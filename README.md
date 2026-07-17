# Invoice Triage Copilot

A multi-agent AI system that reads vendor invoices and decides — automatically — whether they are safe to pay or need a human to review them. Built as a capstone for the **5-Day AI Agents Intensive Vibe Coding Course** (Google/Kaggle).

**Track:** Agents for Business  
**Demonstrates:** All 5 course days — ADK multi-agent system, custom MCP server, Agent Skills, full security policy server, evaluation harness with LLM-as-judge

---

## What it does

Paste a raw vendor invoice (text, email copy, OCR output) into the system. Three AI agents work together:

1. **Extraction agent** reads the invoice and pulls out structured fields (vendor, amount, PO number, date)
2. **Validation agent** checks those fields against a purchase-order database, flags any anomalies
3. **Orchestrator** produces a final `approve` or `hold_for_review` recommendation with a plain-English explanation

Anomalies caught: duplicate invoices, amounts more than 10% above the approved PO, closed POs being re-billed, vendor name mismatches, missing PO references, extraction failures.

---

## Quick demo (no API key needed)

```bash
git clone https://github.com/ajoys24/invoice-triage-copilot.git
cd invoice-triage-copilot
pip install -r requirements.txt
python run_demo.py
```

---

## Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.10 or higher | 3.12 recommended |
| pip | any recent | comes with Python |
| Gemini API key | optional | only needed for live agent calls |

---

## Step-by-step setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/ajoys24/invoice-triage-copilot.git
cd invoice-triage-copilot
```

### Step 2 — Create a virtual environment

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

Installs: `google-adk`, `mcp`, `PyYAML`, and the OpenTelemetry SDK. No GPU, no Docker, no cloud account needed for the offline demo.

### Step 4 — Run the offline demo

```bash
python run_demo.py
```

**Expected output — four sections:**

**Section 1** — multi-agent pipeline decisions:
```
STEP 1 — Multi-agent pipeline (Days 1, 2, 3)
  Clean — should approve
    → recommendation: approve  flags: []
  Amount 21% over PO — hold
    → recommendation: hold_for_review  flags: ['amount_exceeds_po']
  Closed PO — hold
    → recommendation: hold_for_review  flags: ['po_already_closed']
  Missing PO reference — hold
    → recommendation: hold_for_review  flags: ['missing_po_reference']
  Duplicate INV-9001 — hold
    → recommendation: hold_for_review  flags: ['duplicate_invoice']
```

**Section 2** — policy server blocking and PII masking:
```
STEP 2 — Policy Server (Day 4)
[Structural] lookup_po (read-only)
  allowed=True  |  Structural check passed.
[Structural] send_approval_email (blocked)
  allowed=False  |  Tool is hard-blocked in environment 'local_dev'...
[Context hygiene] PII masking
  before: {'recipient': 'vendor@acme.com', ...}
  after:  {'recipient': '[[MASKED_EMAIL]]', ...}
```

**Section 3** — OpenTelemetry spans and session outcome:
```
STEP 3 — Observability
{"event": "session_outcome", "turns_to_convergence": 2,
 "tool_calls": ["check_duplicate_invoice", "lookup_po"],
 "recommendation": "approve", "trust_decay_signal": false}
```

**Section 4** — 30-case evaluation results:
```
STEP 4 — Eval harness (Day 5): 30-case golden dataset
EVAL SUMMARY — 30 cases
  Unit checks:        30/30 (100%)
  Trajectory checks:  30/30 (100%)
  pass^3:            30/30 (100%)
  Avg judge score:    5.00/5
```

### Step 5 — Run with a live Gemini API key (optional)

Get a free key at: https://aistudio.google.com/app/apikey

```bash
# macOS / Linux
export GOOGLE_API_KEY=your_key_here
python run_demo.py

# Windows (PowerShell)
$env:GOOGLE_API_KEY = "your_key_here"
python run_demo.py
```

With a real key, Step 1 shows actual Gemini model output.

---

## Run individual modules

Each module is independently runnable:

```bash
# Policy server — security checks, no API key needed
python policy/policy_server.py

# Observability tracer — OTel spans as JSON, no API key needed
python observability/tracer.py

# Eval harness — all 30 cases, no API key needed
python evals/run_evals.py

# MCP server — starts on stdio (connect any MCP client)
python mcp/po_database_mcp.py

# PO database tools — quick function test
python -c "
from agents.po_database import lookup_po, check_duplicate_invoice
print(lookup_po('PO-1001'))
print(lookup_po('PO-9999'))
print(check_duplicate_invoice('INV-001'))
print(check_duplicate_invoice('INV-001'))
"
```

---

## Project structure

```
invoice-triage-copilot/
├── AGENTS.md                        # Day 1: harness spec, model routing, hard rules
├── requirements.txt
├── agents/
│   ├── orchestrator_agent.py        # Day 1: routes extraction → validation → result
│   ├── extraction_agent.py          # Day 1: gemini-flash, no tools, JSON out
│   ├── validation_agent.py          # Day 1: gemini-pro, calls MCP tools
│   └── po_database.py               # In-process fallback when MCP not running
├── mcp/
│   └── po_database_mcp.py           # Day 2: custom MCP server over stdio
├── skills/
│   ├── invoice-triage/SKILL.md      # Day 3: main triage skill
│   ├── vendor-lookup/SKILL.md       # Day 3: vendor exposure lookup skill
│   └── exception-escalation/SKILL.md  # Day 3: escalation routing skill
├── policy/
│   ├── policies.yaml                # Day 4: role x environment x tool rules
│   └── policy_server.py            # Day 4: structural + semantic gate + PII masking
├── evals/
│   ├── golden_dataset.json          # Day 5: 30 test cases
│   └── run_evals.py                 # Day 5: unit + trajectory + LLM-judge + pass^k
├── observability/
│   └── tracer.py                    # Day 5: session/think/tool OTel spans
└── run_demo.py                      # Main entrypoint
```

---

## Course concepts map

| Day | Topic | File |
|-----|-------|------|
| 1 | AGENTS.md + model routing | `AGENTS.md`, `agents/*.py` |
| 2 | Custom MCP server (stdio) | `mcp/po_database_mcp.py` |
| 3 | 3 Agent Skills + 30-case golden dataset | `skills/`, `evals/golden_dataset.json` |
| 4 | Hybrid Policy Server + context hygiene | `policy/` |
| 5 | LLM-as-judge eval + OTel observability | `evals/run_evals.py`, `observability/tracer.py` |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'google.adk'`**  
Activate your virtual environment first: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\Activate.ps1` (Windows), then `pip install -r requirements.txt`.

**`ModuleNotFoundError: No module named 'policy'` when running a sub-module**  
Always run from the project root folder: `cd invoice-triage-copilot`, then `python policy/policy_server.py`. Never `cd` into a subfolder first.

**Step 1 shows `[No API key]` after I set the key**  
The env var must be set in the same terminal session. Open a fresh terminal, activate the venv, export the key, then run.

**OTel connection warnings in the output**  
Harmless — means no Jaeger collector is running. Spans are still tracked in-memory. To suppress, don't set `OTEL_EXPORTER_OTLP_ENDPOINT`.

---

## License

MIT
