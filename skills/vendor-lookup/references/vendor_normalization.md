# Vendor name normalization

When matching an invoice vendor name against PO vendor names, apply these
rules to avoid false mismatches:

## Legal-entity suffix stripping
Strip the following suffixes before comparing (case-insensitive):
`Inc`, `Inc.`, `LLC`, `LLC.`, `Ltd`, `Ltd.`, `Co`, `Co.`, `Corp`,
`Corp.`, `GmbH`, `Pvt`, `Pvt.`, `Private Limited`, `PLC`

Example: "Acme Office Supplies Inc." matches "Acme Office Supplies"

## Case normalization
Always compare lowercased strings after suffix stripping.

## Ampersand / "and" equivalence
Treat `&` and `and` as equivalent.
Example: "Smith & Co" matches "Smith and Co"

## When mismatch remains after normalization
If the vendor name still does not match after normalization, flag
`vendor_mismatch` in the invoice-triage skill. Do not attempt fuzzy
matching or phonetic matching — surface the discrepancy to a human.
