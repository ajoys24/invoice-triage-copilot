---
name: vendor-lookup
description: |
  Looks up open purchase orders for a named vendor and summarises their
  outstanding invoice exposure. Use when the user asks "what POs do we
  have with [vendor]", "how much is outstanding with [vendor]", or
  "list all open orders for [vendor]". Do NOT use to validate a specific
  invoice against a PO — that is the invoice-triage skill.
version: 1.0.0
license: MIT
allowed-tools: lookup_po list_open_pos
metadata:
  author: invoice-triage-copilot
  requires-mcp: po-database-mcp
---

# Vendor lookup

## When to use
- Building a vendor exposure summary before a payment run
- Checking whether a vendor has any open POs before onboarding them again
- Answering "what's our outstanding liability with X?"

## When NOT to use
- Validating a specific invoice (use invoice-triage)
- Generating full spend analytics or trend reports

## Workflow

1. Call `list_open_pos()` to retrieve all open purchase orders.
2. Filter to POs where `vendor` matches the requested vendor name.
   Use case-insensitive matching; see `references/vendor_normalization.md`
   for handling legal-entity suffix variants (Inc., LLC, Ltd., Co.).
3. Sum `approved_amount` across matched POs for total exposure.
4. Format output using `assets/vendor_summary_template.md`.

## Examples
- "What POs do we have with Acme?" → list PO-1001 ($1,200 open)
- "Outstanding with Bright Cloud?" → PO-1002 ($4,500 open)
- "Any orders for Unknown Co?" → no open POs found

## Anti-patterns to avoid
- Do not call `lookup_po` in a loop for each PO — call `list_open_pos`
  once and filter in memory
- Do not invent PO numbers if none are found — return empty list
