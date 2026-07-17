# Invoice Triage Copilot: A Multi-Agent AI System for Autonomous Vendor Invoice Validation

**Subtitle:** From raw invoice text to approve/hold decision in seconds — a production-grade multi-agent system built across all five days of the AI Agents Intensive

**Track:** Agents for Business

---

## The Problem

Every finance and operations team shares a version of the same bottleneck: vendor invoices arrive daily by email, PDF, or supplier portal, and someone has to read each one, cross-check it against the purchase order system, spot any anomalies, and route it for payment or escalation. In small teams this is a manual, error-prone process. Common failures include:

- Duplicate invoices submitted by the same vendor, resulting in double payments
- Invoices that exceed the approved purchase order amount by amounts that slip past a tired reviewer
- Invoices referencing closed or non-existent PO numbers
- Vendor name mismatches that indicate a substitution or billing error

These are not subtle judgment calls. They are rule-based checks that a well-designed agent can perform faster, more consistently, and with a full audit trail. The Invoice Triage Copilot automates exactly this workflow.

---

## What It Does

The system accepts a raw vendor invoice — pasted text, OCR output, or email content — and returns one of two outcomes within seconds:

- **Approve**: the invoice is clean, all checks passed, safe to proceed to the standard payment process
- **Hold for Review**: one or more anomalies were detected, each flag described in plain language, with an escalation path routing the invoice to the correct human reviewer

Seven anomaly types are detected: duplicate invoice numbers, amounts more than 10% above the approved PO, closed POs being re-billed, vendor name mismatches between the invoice and the PO, missing PO references, unresolvable PO numbers, and extraction failures where a required field could not be read from the invoice text.

When an invoice is held, the system also determines escalation routing: an AP Clerk for low-value missing-reference cases, a Finance Manager for structural issues, or the CFO for high-value or fraud-risk patterns. This routing logic lives in a dedicated Agent Skill, not hardcoded in agent instructions, making it independently maintainable by the finance team without touching any code.

---

## Architecture: All Five Course Days in One System

The project is intentionally scoped to demonstrate every concept from the five-day curriculum, not just multi-agent orchestration. Here is how each day maps to a concrete implementation artifact.

### Day 1 — Spec-Driven Harness and Model Routing

The project's `AGENTS.md` file defines the stack, conventions, and hard rules the agent must never break — following the Day 1 principle that the spec, not the prompt, is the contract. It also defines an explicit model routing table:

| Task | Model | Reason |
|------|-------|--------|
| Invoice field extraction | gemini-flash-latest | Deterministic parsing, no reasoning needed — 5× cheaper |
| PO validation and flagging | gemini-pro | Multi-step reasoning, tool calls, compound logic |
| Semantic policy check | gemini-flash-latest | Single-prompt classification, latency-sensitive |
| LLM-as-judge eval scoring | gemini-pro | Nuanced rubric judgment |

This is not about using the most powerful model everywhere — it is about using the right model for each task's complexity, exactly as the Day 1 whitepaper argues.

### Day 2 — Custom MCP Server

The purchase-order database is exposed as a proper MCP server (`mcp/po_database_mcp.py`) over stdio transport, not as bespoke in-process functions. The server exposes three read-only tools: `lookup_po`, `check_duplicate_invoice`, and `list_open_pos`.

The Day 2 rationale for MCP is that it reduces N×M integration complexity to N+M: any future agent on any runtime can consume these tools without re-wiring. The server is deliberately read-only, following the Day 2 best practice of not using MCP servers for writes in prototyping and development.

### Day 3 — Three Agent Skills and a 30-Case Golden Dataset

Three SKILL.md files follow the canonical structure defined in Day 3 — frontmatter with trigger description and allowed tools, workflow steps, worked examples, and explicit anti-patterns:

- **invoice-triage**: the main validation skill, triggered on "validate invoice" or "check PO"
- **vendor-lookup**: triggered on "what POs do we have with [vendor]" or "outstanding with"
- **exception-escalation**: triggered on "who should review this" or "escalation path" — pure logic, no tools, rules live in a reference file the finance team owns

The evaluation dataset has 30 cases stored in `evals/golden_dataset.json`, covering all flag combinations, boundary conditions (exactly 10% over, exactly 10.01% over), OCR noise, vendor suffix normalisation (Inc., LLC, Ltd.), and explicit negative cases — queries that must not trigger any skill. The Day 3 checklist requires both positive and negative trigger cases; five of the 30 cases are deliberate negatives.

### Day 4 — Full Security Implementation

The security layer implements three concepts from Day 4's seven-pillar framework:

**Structural gating (Pillar 4):** A deterministic YAML lookup in `policy/policies.yaml` checks every tool call against a role × environment × tool matrix before execution. The `triage_agent` role can call `lookup_po` and `check_duplicate_invoice` freely, but `send_approval_email` and `mark_invoice_paid` require human approval and are hard-blocked in the `local_dev` environment regardless of approval. This is the "traffic lights" layer — no LLM, instant, impossible for a prompt to bypass.

**Semantic gating (Pillar 4):** A secondary LLM acts as an intelligent referee, inspecting proposed tool arguments for PII leaks and prompt injection that regex cannot catch. An admin role may be allowed to call `send_approval_email`, but the semantic gate blocks it if the argument contains an unmasked vendor email address.

**Context hygiene (Pillar 5 / Day 5):** `sanitize_tool_args()` runs before any tool call or log entry, replacing email addresses, card numbers, SSNs, and credentials with `[[MASKED_EMAIL]]`, `[[MASKED_CARD]]` placeholders. The Day 5 whitepaper calls this the context hallucination defence — an agent that lacks specific data will fill gaps from its context; masking PII before it enters the context prevents it from leaking in generated output.

The confused deputy guard (Pillar 5) is implemented through explicit role presentation: every policy check requires the caller to state their role. There is no ambient permission inheritance from the calling context.

### Day 5 — Evaluation Harness and Observability

The `evals/run_evals.py` harness implements the full Day 5 evaluation toolkit:

**Unit check:** Did the correct skill trigger? Were the correct flags raised? Was the recommendation correct?

**Trajectory check:** Did the agent call tools in the right sequence? A tolerance of one out-of-order swap is permitted — the Day 5 spec notes that trajectory-aware scoring should tolerate ordering variance in non-critical sequences.

**LLM-as-judge with position swapping:** The judge scores each output on a 0–5 rubric against two non-negotiables from the Day 3 whitepaper: swap the A/B positions between two scoring calls to neutralise ordering bias, and flag cases where the two scores diverge by more than one point as unreliable judge signals.

**pass^k runner:** Each case runs k=3 times; all three must pass. The Day 3 data on pass^1 vs pass^8 degradation makes this requirement clear — a single lucky pass is not a production reliability signal.

The observability layer (`observability/tracer.py`) wraps every agent lifecycle event in OpenTelemetry spans using the three types from Day 4's Pillar 6: `agent.session` for the entire triage run, `agent.think` for each sub-agent deliberation, and `agent.tool` for each MCP tool call with PII-masked arguments. When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, spans export to Jaeger, Cloud Trace, or Datadog. In local development they are captured in-memory without network noise. A `SessionTracker` records turns-to-convergence, total tool calls, and a trust-decay signal that fires when the agent self-repairs more than twice in one session.

---

## Architectural Decisions Worth Explaining

**Internal specialisation, not A2A.** The three agents share one ADK runtime and one session. This was a deliberate choice: A2A adds value when crossing organisational boundaries or when sub-agents need to pause and negotiate across a multi-turn interruption. This workflow has neither. Choosing the right tool for the problem is a Day 2 principle; using A2A here would be adding protocol overhead for a problem the project does not have.

**The 10% tolerance band is configurable by design.** The anomaly threshold for `amount_exceeds_po` is documented in `skills/invoice-triage/references/anomaly_rules.md`, not hardcoded in agent instructions. A finance team can change the threshold by editing a markdown file. This is the Day 3 progressive-disclosure pattern applied to business rules: the skill body contains the logic flow, the references directory contains the parameters that domain owners need to tune.

**The escalation skill has zero tools.** The entire escalation routing logic — AP Clerk, Finance Manager, CFO thresholds — lives in `skills/exception-escalation/references/escalation_matrix.md`. No tool calls are needed because the logic is deterministic from the flag list and invoice amount. This is not a limitation; it is the correct architecture for rules that a finance manager should be able to read, understand, and modify without touching code.

---

## Results

Running `python run_demo.py` against the 30-case golden dataset with offline stub responses:

- Unit checks: 30/30 (100%)
- Trajectory checks: 30/30 (100%)
- pass^3: 30/30 (100%)
- Average judge score: 5.00/5 (offline stub)

With a live Gemini API key, the system correctly triages all five sample invoices: clean approval, amount overage hold, closed-PO hold, missing-PO hold, and duplicate detection — each with a correct flag list and plain-English explanation suitable for a finance reviewer to act on immediately.

---

## What I Would Add With More Time

The project README is honest about scope cuts. Three additions would make this production-grade:

**Real ERP integration.** The MCP server currently connects to an in-memory dictionary. The same server interface, with a live database cursor substituted for `_PO_DB`, would connect to NetSuite, SAP, or QuickBooks with no changes to the agent code — which is exactly the MCP value proposition.

**Canary and shadow mode.** The eval harness runs offline against the golden dataset. Shadow mode would run the agent in parallel with the current manual process on 1% of live invoices, comparing agent recommendations against human decisions to build a real ground-truth dataset.

**Full AgBOM trust tracking.** The `SessionTracker.trust_decay_signal` is a simple heuristic (more than two self-repairs in one session). A production system would track a Runtime Agent Bill of Materials continuously, as described in Day 4's Pillar 6, flagging intent drift when the agent's tool call sequence diverges from the pattern established in the golden dataset.

---

## Code Repository

All code is publicly available at: **https://github.com/ajoys24/invoice-triage-copilot**

The repository includes setup instructions, a requirements file tested on Python 3.12, and an offline demo mode that runs the full four-step demonstration without any API key. The README maps every file to the course day it demonstrates.

---

*Built solo as a capstone for the 5-Day AI Agents Intensive Vibe Coding Course with Google (June 2026). Total implementation time: approximately two focused evenings.*
