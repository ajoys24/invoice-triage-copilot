# Escalation matrix

## Escalation tiers (lowest to highest)
1. **AP Clerk** — routine anomalies, low dollar value
2. **Finance Manager** — structural issues, moderate value
3. **CFO** — high-value, fraud-risk, or multi-flag cases

## Flag-based routing

### duplicate_invoice
- Always: AP Clerk (place on immediate hold; do not re-route to manager
  unless the duplicate amount exceeds $5 000, in which case add Finance
  Manager as a secondary reviewer)

### po_not_found
- Invoice amount < $500: AP Clerk
- $500 – $5 000: Finance Manager
- > $5 000: CFO

### amount_exceeds_po
- Overage amount (invoice − approved) < $500: Finance Manager
- Overage amount ≥ $500: CFO

### po_already_closed
- Always: Finance Manager + add "potential re-billing risk" note
- If invoice amount > $2 000: also notify CFO

### vendor_mismatch
- Always: Finance Manager (vendor contract verification required)

### missing_po_reference
- Invoice amount < $200: AP Clerk (may be petty cash or receipt)
- Invoice amount ≥ $200: Finance Manager

### extraction_failure
- Always: AP Clerk (manual review of original document required)

## Multi-flag escalation
Take the highest tier required by any individual flag. Then:
- 3+ flags: always CC Finance Manager regardless of individual tiers
- Any combination including `po_already_closed` + `amount_exceeds_po`:
  always escalate to CFO and flag for audit team
