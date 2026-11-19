"""Batch triage from a CSV.
  python triage_file.py invoices.csv          offline (uses the structured columns)
  python triage_file.py invoices.csv --llm    online (Gemini reads the raw_text column)
"""
import csv, json, os, re, sys, time
from agents.po_database import lookup_po, check_duplicate_invoice

def norm_po(p):
    m = re.search(r"(\d{3,})", str(p)) if p else None
    return f"PO-{m.group(1)}" if m else None

def validate(f):
    flags = []
    if check_duplicate_invoice(f["invoice_number"])["is_duplicate"]:
        flags.append("duplicate_invoice")
    po_ref = norm_po(f.get("po_number"))
    if not po_ref:
        flags.append("missing_po_reference")
    else:
        po = lookup_po(po_ref)
        if not po["found"]:
            flags.append("po_not_found")
        else:
            if po["status"] == "closed": flags.append("po_already_closed")
            if po.get("vendor", "").lower() != f["vendor"].lower(): flags.append("vendor_mismatch")
            if f["amount"] > po["approved_amount"] * 1.10: flags.append("amount_exceeds_po")
    return flags

def llm_extract(text, client, types, tries=4):
    prompt = ('Extract JSON only: {"invoice_number": str, "vendor": str, "po_number": str or null, "amount": number}. '
              'po_number like PO-1001; null if absent.\nInvoice text:\n' + text)
    for i in range(tries):
        try:
            r = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            return json.loads(r.text)
        except Exception as e:
            if i == tries - 1: raise
            print(f"  (API busy, retrying in {10*(i+1)}s)"); time.sleep(10 * (i + 1))

path = sys.argv[1]
use_llm = "--llm" in sys.argv
client = types = None
if use_llm:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
print(f"\nMode: {'ONLINE (Gemini reads raw_text)' if use_llm else 'OFFLINE (structured columns)'}  |  {len(rows)} invoices\n")
print(f"{'INVOICE':<10}{'VENDOR':<26}{'PO':<9}{'AMOUNT':>9}  {'DECISION':<16}FLAGS")
out = []
for row in rows:
    if use_llm and row.get("raw_text"):
        f = llm_extract(row["raw_text"], client, types)
        time.sleep(2)
    else:
        f = {"invoice_number": row["invoice_number"], "vendor": row["vendor"],
             "po_number": row.get("po_number") or None,
             "amount": row["amount"]}
    f["amount"] = float(str(f["amount"]).replace(",", "").replace("$", ""))
    flags = validate(f)
    rec = "hold_for_review" if flags else "approve"
    print(f"{f['invoice_number']:<10}{f['vendor']:<26}{str(norm_po(f.get('po_number')) or '-'):<9}{f['amount']:>9,.0f}  {rec:<16}{flags}")
    out.append({**f, "decision": rec, "flags": ";".join(flags)})

with open("triage_results.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print("\nSaved: triage_results.csv")