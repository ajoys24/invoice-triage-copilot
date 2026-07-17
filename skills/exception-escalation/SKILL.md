---
name: exception-escalation
description: |
  Determines the correct human escalation path for a held invoice based on
  the flags raised and the invoice amount. Use when an invoice has been
  held for review and the system needs to decide who should review it:
  AP clerk, finance manager, or CFO. Do NOT use to validate the invoice
  or to actually send the escalation — only to determine the routing.
version: 1.0.0
license: MIT
allowed-tools: []
metadata:
  author: invoice-triage-copilot
---

# Exception escalation routing

## When to use
- After invoice-triage returns `hold_for_review`
- When a reviewer asks "who should approve this?"
- When building an escalation summary for a batch

## When NOT to use
- Before invoice-triage has run (never skip validation)
- To actually send the escalation email (use the HITL checkpoint)
- To approve an invoice (this skill only routes, never approves)

## Routing rules

See `references/escalation_matrix.md` for the full matrix. Summary:

| Flag(s) | Amount | Escalate to |
|---|---|---|
| `duplicate_invoice` | any | AP Clerk (immediate hold) |
| `po_not_found` | < $500 | AP Clerk |
| `po_not_found` | $500 – $5 000 | Finance Manager |
| `po_not_found` | > $5 000 | CFO |
| `amount_exceeds_po` | overage < $500 | Finance Manager |
| `amount_exceeds_po` | overage ≥ $500 | CFO |
| `po_already_closed` | any | Finance Manager + flag for audit |
| `vendor_mismatch` | any | Finance Manager |
| `missing_po_reference` | < $200 | AP Clerk |
| `missing_po_reference` | ≥ $200 | Finance Manager |
| Multiple flags | any | escalate to highest tier across all flags |

## Workflow

1. Receive the flag list and invoice amount from the triage result.
2. Look up each flag in the escalation matrix.
3. Take the highest escalation tier across all flags.
4. Return: `{ "escalate_to": "...", "reason": "...", "flags": [...] }`
5. Format using `assets/escalation_notice_template.md`.

## Anti-patterns to avoid
- Never return a lower tier than what the highest flag requires
- Never escalate to "none" when any flag is present
- Never claim the escalation was sent — only determine the routing
