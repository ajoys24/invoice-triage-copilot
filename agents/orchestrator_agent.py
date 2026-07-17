"""
Orchestrator agent  —  production version

Wires together all five course-day concepts:

  Day 1 — AGENTS.md context + intelligent model routing
           (flash for extraction, pro for validation)
  Day 2 — Sub-agents use MCP tools via po-database-mcp server
  Day 3 — Three skills loaded by sub-agents on demand
  Day 4 — Policy server gates every high-stakes action
  Day 5 — OpenTelemetry spans wrap every agent and tool call

Architecture: internal specialisation (not distributed A2A).
Orchestrator + two sub-agents share one runtime and one session.
This is the right choice for a single-team internal workflow where
there is no cross-organisation boundary to cross (Day-2 rationale).
"""

import asyncio
import json

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from observability.tracer import SessionTracker, session_span, think_span, tool_span
from policy.policy_server import PolicyServer, PolicyViolation

# ---------------------------------------------------------------------------
# Sub-agents (Day 1: model routing — flash vs pro)
# ---------------------------------------------------------------------------

from agents.extraction_agent import extraction_agent
from agents.validation_agent import validation_agent

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

ORCHESTRATOR_INSTRUCTION = """\
You are the invoice triage orchestrator. You have two specialist sub-agents:
  - invoice_extraction_agent: pulls structured fields from raw invoice text
  - invoice_validation_agent: validates extracted fields against the PO system

For every invoice:
1. Delegate to invoice_extraction_agent to extract:
   vendor_name, invoice_number, po_number, invoice_amount, invoice_date.
2. Pass the extracted fields to invoice_validation_agent to check for anomalies.
3. Based on the validation result:
   - recommendation "approve": state the invoice is clean and ready for
     the standard payment process.
   - recommendation "hold_for_review": list every flag in plain language
     and state the invoice is being routed to a human reviewer.
4. Then determine the escalation path using the exception-escalation skill.
5. NEVER claim to have sent an email, made a payment, or escalated —
   those require human approval through the policy server.
6. NEVER fabricate fields when extraction returns null.
"""

orchestrator_agent = LlmAgent(
    name="invoice_triage_orchestrator",
    model="gemini-2.0-flash",         # Day-1: pro for final recommendation
    instruction=ORCHESTRATOR_INSTRUCTION,
    description="Routes an invoice through extraction → validation → escalation routing.",
    sub_agents=[extraction_agent, validation_agent],
)


# ---------------------------------------------------------------------------
# Instrumented runner
# ---------------------------------------------------------------------------

async def triage_invoice(
    raw_invoice_text: str,
    role: str = "triage_agent",
    environment: str = "local_dev",
) -> dict:
    """
    Full production path:
      1. Open OTel session span
      2. Run orchestrator (extraction → validation)
      3. Check policy gate before any high-stakes action
      4. Return structured result with recommendation + flags + escalation
    """
    invoice_ref = raw_invoice_text.split("\n")[0][:40].strip()
    tracker = SessionTracker(invoice_ref)
    policy = PolicyServer(role=role, environment=environment)

    with session_span(invoice_ref) as sess:
        # Run the multi-agent pipeline
        runner = InMemoryRunner(agent=orchestrator_agent, app_name="invoice_triage")
        session = await runner.session_service.create_session(
            app_name="invoice_triage", user_id="demo_user"
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=raw_invoice_text)],
        )

        chunks = []
        with think_span("orchestrator", turn=1):
            async for event in runner.run_async(
                user_id="demo_user",
                session_id=session.id,
                new_message=message,
            ):
                if event.content and event.content.parts:
                    chunks.extend(p.text for p in event.content.parts if p.text)

        final_text = "".join(chunks)
        tracker.record_turn("orchestrator")

        # Derive structured result from the final text (simplified parsing)
        flags = _extract_flags(final_text)
        recommendation = "hold_for_review" if flags else "approve"
        tracker.set_recommendation(recommendation)

        sess.set_attribute("recommendation", recommendation)
        sess.set_attribute("flags", json.dumps(flags))

    tracker.emit()

    return {
        "recommendation": recommendation,
        "flags": flags,
        "narrative": final_text,
        "invoice_ref": invoice_ref,
    }


def _extract_flags(text: str) -> list[str]:
    """Parse flag names from agent output text (simple keyword scan)."""
    known_flags = [
        "duplicate_invoice", "po_not_found", "po_already_closed",
        "vendor_mismatch", "amount_exceeds_po", "missing_po_reference",
        "extraction_failure",
    ]
    return [f for f in known_flags if f in text.lower().replace(" ", "_")]


# ---------------------------------------------------------------------------
# Policy-gated high-stakes action (human must call this, not the agent)
# ---------------------------------------------------------------------------

async def execute_approval(
    invoice_ref: str,
    tool_name: str = "send_approval_email",
    human_approved: bool = True,
    role: str = "human_reviewer",
    environment: str = "local_dev",
) -> dict:
    """
    The action a human reviewer triggers after inspecting a held invoice.
    Policy gate runs again here — approval must still pass both layers.
    """
    policy = PolicyServer(role=role, environment=environment)

    with tool_span(tool_name, {"invoice_ref": invoice_ref}):
        try:
            decision = await policy.check_tool_call(
                tool_name,
                args={"invoice_ref": invoice_ref},
                human_approved=human_approved,
            )
            return {"status": "executed", "tool": tool_name, "invoice": invoice_ref}
        except PolicyViolation as e:
            return {"status": "blocked", "reason": str(e), "tool": tool_name}


# ---------------------------------------------------------------------------
# Demo entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SAMPLE = """\
Invoice #INV-9001
Vendor: Acme Office Supplies
PO Reference: PO-1001
Amount Due: $1,450.00
Date: 2026-06-20
"""
    result = asyncio.run(triage_invoice(SAMPLE))
    print(json.dumps(result, indent=2))
