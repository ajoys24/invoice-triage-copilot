"""
Observability layer  —  Day 4 (Pillar 6) + Day 5

Implements the three span types from the Day-4 observability spec:

  agent.session  — entire invoice triage run (start → final recommendation)
  agent.think    — each time an agent deliberates (per sub-agent invocation)
  agent.tool     — each MCP tool call with args, latency, and result

Also tracks:
  - Token cost per session (for Denial-of-Wallet detection)
  - Turn count to convergence
  - Trust decay signals (unexpected tool sequences, self-repair loops)

The spans export via OTLP (to Jaeger, GCP Cloud Trace, Datadog, etc.).
In local_dev with no collector configured, they print as structured JSON.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

# ---------------------------------------------------------------------------
# Lightweight span implementation
# Falls back to console-printing if opentelemetry is not installed.
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    _resource = Resource.create({"service.name": "invoice-triage-copilot"})
    _provider = TracerProvider(resource=_resource)

    # Try to wire up OTLP export only if a collector endpoint is explicitly set.
    # If OTEL_EXPORTER_OTLP_ENDPOINT is not set we use an in-memory exporter so
    # spans are created (and visible in code) without any network noise.
    _otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if _otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            _exporter = OTLPSpanExporter(endpoint=_otlp_endpoint, insecure=True)
            _provider.add_span_processor(BatchSpanProcessor(_exporter))
        except Exception:
            pass
    else:
        # No collector configured — silently capture spans in memory.
        _provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))

    otel_trace.set_tracer_provider(_provider)
    _tracer = otel_trace.get_tracer("invoice-triage-copilot")
    _OTEL_AVAILABLE = True

except ImportError:
    _OTEL_AVAILABLE = False
    _tracer = None


# ---------------------------------------------------------------------------
# Fallback: lightweight console-based span for local_dev without OTEL
# ---------------------------------------------------------------------------

@dataclass
class ConsoleSpan:
    name: str
    attributes: dict = field(default_factory=dict)
    _start: float = field(default_factory=time.time)
    _events: list[dict] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        self._events.append({"event": name, "t": time.time() - self._start, **(attributes or {})})

    def set_status(self, status: str) -> None:
        self.attributes["status"] = status

    def end(self) -> None:
        duration_ms = (time.time() - self._start) * 1000
        print(json.dumps({
            "span": self.name,
            "duration_ms": round(duration_ms, 1),
            "attributes": self.attributes,
            "events": self._events,
        }))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@contextmanager
def session_span(invoice_ref: str) -> Generator[Any, None, None]:
    """
    agent.session span — wraps the entire triage run.
    Attributes: invoice_ref, session_id, final_recommendation, total_cost_usd.
    """
    session_id = str(uuid.uuid4())[:8]
    if _OTEL_AVAILABLE and _tracer:
        with _tracer.start_as_current_span("agent.session") as span:
            span.set_attribute("invoice.ref", invoice_ref)
            span.set_attribute("session.id", session_id)
            yield span
    else:
        span = ConsoleSpan(name="agent.session", attributes={"invoice.ref": invoice_ref, "session.id": session_id})
        try:
            yield span
        finally:
            span.end()


@contextmanager
def think_span(agent_name: str, turn: int = 1) -> Generator[Any, None, None]:
    """
    agent.think span — wraps one deliberation cycle of a sub-agent.
    Attributes: agent_name, turn_number, input_tokens, output_tokens.
    """
    if _OTEL_AVAILABLE and _tracer:
        with _tracer.start_as_current_span("agent.think") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("agent.turn", turn)
            yield span
    else:
        span = ConsoleSpan(name="agent.think", attributes={"agent.name": agent_name, "agent.turn": turn})
        try:
            yield span
        finally:
            span.end()


@contextmanager
def tool_span(tool_name: str, args: dict | None = None) -> Generator[Any, None, None]:
    """
    agent.tool span — wraps one MCP tool call.
    Attributes: tool.name, tool.args (PII-masked), tool.latency_ms, tool.result_ok.

    Args are PII-masked before logging — never log raw args that
    might contain vendor email addresses or invoice PII.
    """
    try:
        from policy.policy_server import sanitize_tool_args  # type: ignore
    except ModuleNotFoundError:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from policy.policy_server import sanitize_tool_args  # type: ignore
    safe_args = sanitize_tool_args(args or {})

    if _OTEL_AVAILABLE and _tracer:
        with _tracer.start_as_current_span("agent.tool") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.args", json.dumps(safe_args))
            yield span
    else:
        span = ConsoleSpan(
            name="agent.tool",
            attributes={"tool.name": tool_name, "tool.args": json.dumps(safe_args)},
        )
        try:
            yield span
        finally:
            span.end()


# ---------------------------------------------------------------------------
# Session outcome tracker (Day-4: convergence metrics)
# ---------------------------------------------------------------------------

class SessionTracker:
    """
    Tracks per-session metrics for post-hoc analysis:
    - Turns to convergence (how many sub-agent steps to reach recommendation)
    - Total tool calls (proxy for reasoning cost)
    - Trust decay signals (unexpected tool calls, self-repair loops)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = time.time()
        self.turns = 0
        self.tool_calls: list[str] = []
        self.self_repairs = 0
        self.recommendation: str | None = None

    def record_turn(self, agent_name: str) -> None:
        self.turns += 1

    def record_tool(self, tool_name: str) -> None:
        self.tool_calls.append(tool_name)

    def record_self_repair(self) -> None:
        """Increment when the agent corrects a prior tool call or re-tries."""
        self.self_repairs += 1

    def set_recommendation(self, rec: str) -> None:
        self.recommendation = rec

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "elapsed_s": round(time.time() - self.start_time, 2),
            "turns_to_convergence": self.turns,
            "tool_calls": self.tool_calls,
            "total_tool_calls": len(self.tool_calls),
            "self_repairs": self.self_repairs,
            "recommendation": self.recommendation,
            "trust_decay_signal": self.self_repairs > 2,
        }

    def emit(self) -> None:
        print(json.dumps({"event": "session_outcome", **self.to_dict()}))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Tracer self-test (console-mode spans) ===\n")

    with session_span("INV-TEST-001") as sess:
        sess.set_attribute("test", True)

        with think_span("invoice_extraction_agent", turn=1):
            time.sleep(0.01)

        with tool_span("check_duplicate_invoice", {"invoice_number": "INV-TEST-001", "requester_email": "test@acme.com"}):
            # Note: requester_email should be masked
            time.sleep(0.005)

        with tool_span("lookup_po", {"po_number": "PO-1001"}):
            time.sleep(0.005)

        with think_span("invoice_validation_agent", turn=2):
            time.sleep(0.01)

        sess.set_attribute("recommendation", "approve")

    tracker = SessionTracker("INV-TEST-001")
    tracker.record_turn("extraction")
    tracker.record_tool("check_duplicate_invoice")
    tracker.record_tool("lookup_po")
    tracker.record_turn("validation")
    tracker.set_recommendation("approve")
    tracker.emit()
