"""Type any invoice, get an offline triage result. Run: python offline_custom.py"""
from agents.po_database import lookup_po, check_duplicate_invoice

print("Known POs: PO-1001 (Acme Office Supplies), PO-1002 (Bright Cloud Hosting), PO-1003 (closed)")
while True:
    inv = input("\nInvoice number (or 'q' to quit): ").strip()
    if inv.lower() == "q":
        break
    vendor = input("Vendor name: ").strip()
    po_ref = input("PO number (blank if none): ").strip().upper() or None
    amount = float(input("Amount (e.g. 1450): ").replace(",", "").replace("$", ""))

    flags = []
    if check_duplicate_invoice(inv)["is_duplicate"]:
        flags.append("duplicate_invoice")
    if not po_ref:
        flags.append("missing_po_reference")
    else:
        po = lookup_po(po_ref)
        if not po["found"]:
            flags.append("po_not_found")
        else:
            if po["status"] == "closed":
                flags.append("po_already_closed")
            if po.get("vendor", "").lower() != vendor.lower():
                flags.append("vendor_mismatch")
            if amount > po["approved_amount"] * 1.10:
                flags.append("amount_exceeds_po")

    print("\n  -> flags:", flags)
    print("  -> recommendation:", "hold_for_review" if flags else "approve")