"""
In-process PO database — used as fallback when MCP server is not running.

In production, the validation agent uses po-database-mcp over stdio (Day 2).
In local demo mode (no MCP server), this module provides the same tools
as direct Python functions so the rest of the code works without changes.
"""

_PO_DB = {
    "PO-1001": {"po_number": "PO-1001", "vendor": "Acme Office Supplies",  "approved_amount": 1200.00, "status": "open"},
    "PO-1002": {"po_number": "PO-1002", "vendor": "Bright Cloud Hosting",  "approved_amount": 4500.00, "status": "open"},
    "PO-1003": {"po_number": "PO-1003", "vendor": "Acme Office Supplies",  "approved_amount": 800.00,  "status": "closed"},
    "PO-1004": {"po_number": "PO-1004", "vendor": "Delta Logistics Co",    "approved_amount": 2100.00, "status": "open"},
    "PO-1005": {"po_number": "PO-1005", "vendor": "Nexus Software Ltd",    "approved_amount": 9800.00, "status": "open"},
}

_SEEN_INVOICE_NUMBERS: set[str] = set()


def lookup_po(po_number: str) -> dict:
    """Look up a PO by number. Returns the PO record or {"found": False}."""
    po = _PO_DB.get(po_number)
    return {"found": True, **po} if po else {"found": False, "po_number": po_number}


def check_duplicate_invoice(invoice_number: str) -> dict:
    """Check and record whether this invoice number has been seen before."""
    is_duplicate = invoice_number in _SEEN_INVOICE_NUMBERS
    _SEEN_INVOICE_NUMBERS.add(invoice_number)
    return {"invoice_number": invoice_number, "is_duplicate": is_duplicate}


def list_open_pos() -> dict:
    """Return all open purchase orders."""
    return {"open_pos": [po for po in _PO_DB.values() if po["status"] == "open"]}
