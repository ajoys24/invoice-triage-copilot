"""Live demo: Gemini extracts fields from messy invoice text,
deterministic PO tools validate. Run: python live_llm_demo.py"""
import json, os, sys, time
from google import genai
from google.genai import types
from agents.po_database import lookup_po, check_duplicate_invoice

MODEL = "gemini-3.5-flash-lite"
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

PROMPT = """Extract these fields from the invoice text and return ONLY JSON:
{"invoice_number": str, "vendor": str, "po_number": str or null, "amount": number}
Invoice text:
"""

INVOICES = [
 ("Messy but clean", "hi team, pls find attached bill no. INV-7001 from Bright Cloud Hosting against PO-1002, total due USD 4,500.00. thanks!"),
 ("Overage", "INVOICE INV-7002 // Acme Office Supplies // ref PO 1001 // Amount Due: $1,450.00"),
 ("No PO", "Bill #INV-7003 from New Vendor Co, amount $300. Please pay soon."),
]

def validate(f):
    flags = []
    if check_duplicate_invoice(f["invoice_number"])["is_duplicate"]:
        flags.append("duplicate_invoice")
    if not f.get("po_number"):
        flags.append("missing_po_reference")
    else:
        po = lookup_po(f["po_number"])
        if not po["found"]:
            flags.append("po_not_found")
        else:
            if po["status"] == "closed": flags.append("po_already_closed")
            if po.get("vendor", "").lower() != f["vendor"].lower(): flags.append("vendor_mismatch")
            if f["amount"] > po["approved_amount"] * 1.10: flags.append("amount_exceeds_po")
    return flags

for label, text in INVOICES:
    print("\n" + "=" * 60 + f"\n{label}\n" + "=" * 60)
    print("RAW TEXT :", text)
    t = time.time()
    r = client.models.generate_content(
        model=MODEL, contents=PROMPT + text,
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    fields = json.loads(r.text)
    print(f"LLM EXTRACTED ({time.time()-t:.1f}s):", fields)
    flags = validate(fields)
    print("TOOL FLAGS   :", flags)
    print("RECOMMENDATION:", "hold_for_review" if flags else "approve")
    time.sleep(2)