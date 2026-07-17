"""
Full demo runner  —  all 5 days in one execution trace

Run:  python run_demo.py

What it shows (in order):
  Step 1 — Agent pipeline (Days 1 + 2 + 3)
            5 invoices through extraction → validation → escalation routing
            Model routing: flash for extraction, pro for validation

  Step 2 — Policy Server (Day 4)
            Structural check: role × environment × tool
            Semantic check: LLM referee (skipped if no API key)
            Context hygiene: PII masking on tool arguments

  Step 3 — Observability (Days 4 + 5)
            Session, think, and tool spans printed as JSON
            Session outcome tracker: turns, tool calls, trust decay signal

  Step 4 — Eval harness (Day 5)
            Offline: 30 golden dataset cases, unit + trajectory checks
            (LLM-as-judge and pass^k use stub scores without API key)
"""

import asyncio
import json

INVOICES = [
    {"label": "Clean — should approve",
     "text": "Invoice #INV-9001\nVendor: Bright Cloud Hosting\nPO: PO-1002\nAmount: $4,500.00\nDate: 2026-06-15"},
    {"label": "Amount 21% over PO — hold",
     "text": "Invoice #INV-9002\nVendor: Acme Office Supplies\nPO: PO-1001\nAmount: $1,450.00\nDate: 2026-06-15"},
    {"label": "Closed PO — hold",
     "text": "Invoice #INV-9003\nVendor: Acme Office Supplies\nPO: PO-1003\nAmount: $800.00\nDate: 2026-06-16"},
    {"label": "Missing PO reference — hold",
     "text": "Invoice #INV-9004\nVendor: New Vendor Co\nAmount: $300.00\nDate: 2026-06-16"},
    {"label": "Duplicate INV-9001 — hold",
     "text": "Invoice #INV-9001\nVendor: Bright Cloud Hosting\nPO: PO-1002\nAmount: $4,500.00\nDate: 2026-06-15"},
]


async def demo_agents():
    print("\n" + "=" * 65)
    print("STEP 1 — Multi-agent pipeline (Days 1, 2, 3)")
    print("=" * 65)

    import os
    has_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))

    if has_key:
        from agents.orchestrator_agent import triage_invoice
        for inv in INVOICES:
            print(f"\n--- {inv['label']} ---")
            result = await triage_invoice(inv["text"])
            print(f"  Recommendation: {result['recommendation']}")
            print(f"  Flags: {result['flags']}")
    else:
        print("\n[No API key — showing expected outcomes from golden dataset]\n")
        expected = ["approve", "hold_for_review", "hold_for_review", "hold_for_review", "hold_for_review"]
        flags_expected = [[], ["amount_exceeds_po"], ["po_already_closed"], ["missing_po_reference"], ["duplicate_invoice"]]
        for inv, rec, flags in zip(INVOICES, expected, flags_expected):
            print(f"  {inv['label']}")
            print(f"    → recommendation: {rec}  flags: {flags}")


async def demo_policy():
    print("\n" + "=" * 65)
    print("STEP 2 — Policy Server (Day 4): structural + semantic + PII masking")
    print("=" * 65)

    from policy.policy_server import PolicyServer, PolicyViolation, sanitize_tool_args

    server = PolicyServer(role="triage_agent", environment="local_dev")

    print("\n[Structural] lookup_po (read-only, should pass)")
    d = server.structural_check("lookup_po")
    print(f"  allowed={d.allowed}  |  {d.reason}")

    print("\n[Structural] send_approval_email without approval (should block)")
    d = server.structural_check("send_approval_email", human_approved=False)
    print(f"  allowed={d.allowed}  |  {d.reason}")

    print("\n[Structural] send_approval_email in local_dev (env-blocked regardless)")
    d = server.structural_check("send_approval_email", human_approved=True)
    print(f"  allowed={d.allowed}  |  {d.reason}")

    print("\n[Context hygiene] PII masking before tool args are logged")
    raw = {"recipient": "vendor@acme.com", "invoice_ref": "INV-9001", "amount": 4500}
    clean = sanitize_tool_args(raw)
    print(f"  before: {raw}")
    print(f"  after:  {clean}")

    print("\n[Semantic] skip (no GOOGLE_CLOUD_PROJECT in local_dev)")
    d = await server.semantic_check("lookup_po", {"po_number": "PO-1001"})
    print(f"  allowed={d.allowed}  |  {d.reason}")


def demo_observability():
    print("\n" + "=" * 65)
    print("STEP 3 — Observability (Days 4, 5): OTel spans + session tracker")
    print("=" * 65)

    import time
    from observability.tracer import SessionTracker, session_span, think_span, tool_span

    print("\n[Spans emitted as JSON — in prod these go to OTLP/Jaeger/Cloud Trace]")
    with session_span("INV-9001") as sess:
        with think_span("invoice_extraction_agent", turn=1):
            time.sleep(0.005)
        with tool_span("check_duplicate_invoice", {"invoice_number": "INV-9001"}):
            time.sleep(0.002)
        with tool_span("lookup_po", {"po_number": "PO-1002"}):
            time.sleep(0.002)
        with think_span("invoice_validation_agent", turn=2):
            time.sleep(0.005)
        sess.set_attribute("recommendation", "approve")

    tracker = SessionTracker("INV-9001")
    tracker.record_turn("extraction")
    tracker.record_tool("check_duplicate_invoice")
    tracker.record_tool("lookup_po")
    tracker.record_turn("validation")
    tracker.set_recommendation("approve")
    print("\n[Session outcome]")
    tracker.emit()


async def demo_evals():
    print("\n" + "=" * 65)
    print("STEP 4 — Eval harness (Day 5): 30-case golden dataset")
    print("=" * 65)

    from evals.run_evals import load_cases, print_summary, run_all_evals
    results = await run_all_evals(k=3, verbose=False)
    print_summary(results, k=3)


async def main():
    await demo_agents()
    await demo_policy()
    demo_observability()
    await demo_evals()
    print("\n" + "=" * 65)
    print("Demo complete. Set GOOGLE_API_KEY to run live agent calls.")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
