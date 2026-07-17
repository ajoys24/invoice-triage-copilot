# Invoice Triage Copilot — Agent Harness Spec

This file is the project's DNA. Every agent and coding tool that touches
this repo reads it. Per Day-1 best practice: start with 10 lines of
essentials, add a rule every time an agent does something it shouldn't.

## Stack

- Runtime: google-adk (LlmAgent, InMemoryRunner)
- Models: gemini-flash-latest (fast, cheap tasks) / gemini-pro-latest (reasoning tasks)
- Tool protocol: MCP stdio (mcp/ directory) — no raw function tools in prod agents
- Skills: skills/ directory, SKILL.md convention from agentskills.io
- Security: policy/policy_server.py (structural + semantic gating)
- Observability: observability/tracer.py (OpenTelemetry, OTLP export)
- Evals: evals/ directory (golden dataset + LLM-as-judge + pass^k runner)

## Model routing rules (Day-1: intelligent model routing)

| Task | Model | Reason |
|------|-------|--------|
| Invoice field extraction | gemini-flash-latest | Deterministic OCR/parse — no reasoning needed |
| PO validation + anomaly flagging | gemini-pro-latest | Multi-step reasoning, tool calls |
| Semantic policy check | gemini-flash-latest | Single-prompt classification, latency-sensitive |
| LLM-as-judge eval scoring | gemini-pro-latest | Nuanced rubric judgment |

Rule: never use pro for extraction — it costs 5× and adds no accuracy.
Rule: never use flash for the final triage recommendation — it misses
      multi-flag compound cases.

## Hard rules (the agent must never violate these)

1. Never claim to have sent an email or marked an invoice paid — those
   actions require human approval and are gated by the policy server.
2. Never fabricate a PO number, vendor name, or amount when extraction
   returns null — treat null as a flag, not a gap to fill.
3. Never call lookup_po with a PO number the extraction agent did not
   explicitly return. Pattern-matching on strings is not extraction.
4. Never store or log raw invoice text that contains vendor PII in
   plain form — run it through the context hygiene sanitizer first.
5. Never bypass the policy server check, even for "test" or "demo" runs.
   The environment flag controls what is blocked, not a code shortcut.

## Context engineering notes

- SKILL.md metadata is always in context (cheap). Skill bodies load only
  on trigger — keep them under 5 000 tokens.
- The PO database is accessed only via MCP, never imported directly by
  agents. This keeps the tool surface auditable.
- Session state is scoped per invoice. Do not carry PO lookups from one
  invoice run into the next.

## Workflow (for any coding agent working in this repo)

1. Write/update evals BEFORE changing agent instructions.
2. Run `python evals/run_evals.py` and confirm pass^3 before committing.
3. Any change to policy/policies.yaml requires a comment explaining the
   business reason for the rule change.
4. Observability spans must cover every tool call — do not add a tool
   without adding a span around it.
