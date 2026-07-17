"""
Extraction sub-agent

Day-1 model routing: uses gemini-flash-latest.
Rationale (from AGENTS.md): extraction is a deterministic OCR/parse task
with no multi-step reasoning. Flash costs 5× less than pro and adds no
accuracy benefit here.

Tool surface: zero. This agent reasons over text only.
Blast radius: none — it cannot call any external service.
"""

from google.adk.agents import LlmAgent
from google.adk.models import Gemini

EXTRACTION_INSTRUCTION = """\
You are an invoice field extraction specialist. Your only job is to turn
unstructured invoice text into structured fields. You do not validate,
look anything up, or make recommendations.

Extract exactly these five fields:
  vendor_name      — the supplier's business name as printed
  invoice_number   — the invoice reference number
  po_number        — the purchase order number referenced (if any)
  invoice_amount   — numeric amount only, no currency symbol
  invoice_date     — in YYYY-MM-DD format if possible

Rules:
- Return a single JSON object with exactly these five keys.
- If a field is unreadable or missing, return null for that key.
- Never guess, pattern-match, or infer a missing field.
- For invoice_amount: parse "$1,450.00" as 1450.00 (float, no commas).
- For invoice_date: normalise to YYYY-MM-DD where possible; null if ambiguous.
"""

extraction_agent = LlmAgent(
    name="invoice_extraction_agent",
    model=Gemini(model="gemini-flash-latest"),   # Day-1: flash for cheap parsing
    instruction=EXTRACTION_INSTRUCTION,
    description=(
        "Extracts vendor_name, invoice_number, po_number, invoice_amount, "
        "and invoice_date from raw invoice text. Returns JSON only. "
        "Does not validate or approve. Has zero tools."
    ),
)
