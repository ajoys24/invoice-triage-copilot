"""
po-database-mcp  —  Day 2: Custom MCP server

Exposes the PO database as a proper MCP server over stdio transport.
This replaces the in-process mock (agents/po_database.py) with a
protocol-compliant server that any MCP-capable agent can consume,
not just this project's ADK agents.

Why MCP instead of a plain function tool?
- The Day-2 whitepaper: MCP reduces N×M integration complexity to N+M.
  Any future agent (different runtime, different vendor) gets this tool
  for free without re-implementing the integration.
- The server is read-only by design (SELECT-only analogy): it exposes
  two query tools, no write tools. The "Don't use it for updates" MCP
  best practice from Day-2 applied literally.
- Tool definitions live in one place; description strings are the routing
  algorithm for every consumer agent.

Transport: stdio (standard for local/prototyping — Day-2 classification)
Run:  python mcp/po_database_mcp.py
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# In-memory data store (replace with real DB connection in production)
# ---------------------------------------------------------------------------

_PO_DB = {
    "PO-1001": {"po_number": "PO-1001", "vendor": "Acme Office Supplies",  "approved_amount": 1200.00, "status": "open"},
    "PO-1002": {"po_number": "PO-1002", "vendor": "Bright Cloud Hosting",  "approved_amount": 4500.00, "status": "open"},
    "PO-1003": {"po_number": "PO-1003", "vendor": "Acme Office Supplies",  "approved_amount": 800.00,  "status": "closed"},
    "PO-1004": {"po_number": "PO-1004", "vendor": "Delta Logistics Co",    "approved_amount": 2100.00, "status": "open"},
    "PO-1005": {"po_number": "PO-1005", "vendor": "Nexus Software Ltd",    "approved_amount": 9800.00, "status": "open"},
}

_SEEN_INVOICE_NUMBERS: set[str] = set()

# ---------------------------------------------------------------------------
# MCP server definition
# ---------------------------------------------------------------------------

server = Server("po-database-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="lookup_po",
            description=(
                "Look up a purchase order by PO number. Returns vendor name, "
                "approved amount, and status (open/closed). Call this whenever "
                "an invoice references a PO number that needs to be verified. "
                "Do NOT call with a fabricated or pattern-matched PO number — "
                "only call with a PO number explicitly extracted from the invoice."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "po_number": {
                        "type": "string",
                        "description": "The PO number as it appears on the invoice, e.g. 'PO-1001'.",
                    }
                },
                "required": ["po_number"],
            },
        ),
        Tool(
            name="check_duplicate_invoice",
            description=(
                "Check whether an invoice number has already been processed in "
                "this session, to catch duplicate submission attempts. Always call "
                "this once per invoice, regardless of whether the invoice has a PO "
                "reference. Records the invoice number as seen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": "The invoice number as printed on the vendor's invoice.",
                    }
                },
                "required": ["invoice_number"],
            },
        ),
        Tool(
            name="list_open_pos",
            description=(
                "List all currently open purchase orders. Use when the invoice "
                "has no PO reference and you need to suggest possible matches, "
                "or when building a summary report of outstanding POs."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "lookup_po":
        po_number = arguments.get("po_number", "")
        po = _PO_DB.get(po_number)
        if po is None:
            result = {"found": False, "po_number": po_number}
        else:
            result = {"found": True, **po}
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "check_duplicate_invoice":
        invoice_number = arguments.get("invoice_number", "")
        is_duplicate = invoice_number in _SEEN_INVOICE_NUMBERS
        _SEEN_INVOICE_NUMBERS.add(invoice_number)
        return [TextContent(type="text", text=json.dumps({
            "invoice_number": invoice_number,
            "is_duplicate": is_duplicate,
        }))]

    elif name == "list_open_pos":
        open_pos = [po for po in _PO_DB.values() if po["status"] == "open"]
        return [TextContent(type="text", text=json.dumps({"open_pos": open_pos}))]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        init_options = server.create_initialization_options()
        await server.run(read, write, init_options)


if __name__ == "__main__":
    asyncio.run(main())
