---
name: invoice-triage
description: |
  Validates a vendor invoice against its purchase order and flags anomalies:
  duplicate submissions, missing PO references, closed POs, vendor name
  mismatches, and amounts exceeding the approved total by more than 10%.
  Use when the user asks to validate an invoice, check an invoice against
  a PO, triage incoming vendor invoices, or process a batch of invoices.
  Do NOT use for employee expense reimbursements, payroll, or anything
  that needs to actually send an approval email or mark a payment — those
  are human-approved actions gated separately by the policy server.
version: 2.0.0
license: MIT
allowed-tools: lookup_po check_duplicate_invoice list_open_pos
metadata:
  author: invoice-triage-copilot
  requires-mcp: po-database-mcp
---

# Invoice triage

## When to use
- A raw invoice (text, email paste, OCR output) needs checking before payment
- A batch of invoices needs splitting into "safe to pay" vs "needs review"
- A reviewer needs a structured summary of all flags before approving

## When NOT to use
- Employee expense reports — different approval chain
- Sending approval emails or marking payments — use the HITL checkpoint
- Generating vendor reports or spend analytics — different skill

## Workflow

1. Extract these fields from the invoice text:
   `vendor_name`, `invoice_number`, `po_number`, `invoice_amount`,
   `invoice_date`. If a field is unreadable, record it as `null`.
   Never guess or pattern-match a missing field.

2. Always call `check_duplicate_invoice(invoice_number)` first.
   - `is_duplicate: true` → flag `duplicate_invoice`

3. If `po_number` is present, call `lookup_po(po_number)`:
   - Not found → flag `po_not_found`
   - Found, `status == "closed"` → flag `po_already_closed`
   - Found, vendor doesn't match → flag `vendor_mismatch`
   - Found, `invoice_amount` > `approved_amount` × 1.10 → flag
     `amount_exceeds_po` (report both amounts)
   - Found, all checks pass → no flag

4. If `po_number` is `null` → flag `missing_po_reference`.
   Optionally call `list_open_pos` to suggest possible matches.

5. If any extracted field is `null` → flag `extraction_failure`
   and do not attempt to approve.

6. See `references/anomaly_rules.md` for the full threshold table
   and edge cases (multiple flags, partial amounts, vendor aliases).

7. Produce output using `assets/approval_template.md`.

## Examples
- Invoice $1,450 vs PO-1001 approved $1,200 (21% over) → `amount_exceeds_po`, hold
- Invoice with no PO number → `missing_po_reference`, hold
- Clean invoice, PO open, amount within 10%, not duplicate → approve
- Second submission of INV-3001 in same session → `duplicate_invoice`, hold

## Anti-patterns to avoid
- Do not approve when `po_number` looks correct but `lookup_po` wasn't called
- Do not normalize amounts before comparison — compare exact figures
- Do not treat `extraction_failure` as a reason to skip flagging
- Do not recommend "approve" when any flag is present
