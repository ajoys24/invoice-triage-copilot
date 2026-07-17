"""
Validation sub-agent

Day-1 model routing: uses gemini-pro-latest.
Rationale (from AGENTS.md): validation requires multi-step reasoning —
call the right tool, interpret ambiguous results, apply threshold rules,
and produce a defensible recommendation. Pro is the right model here.

Day-2: tools are MCP-connected via po-database-mcp server.
Tool surface: two read-only MCP tools (lookup_po, check_duplicate_invoice).

NOTE: In production the tools are registered as MCPToolset entries that
connect to the running po-database-mcp stdio server. For the standalone
demo (no MCP server running) we fall back to direct function imports.
"""

from google.adk.agents import LlmAgent
from google.adk.models import Gemini

VALIDATION_INSTRUCTION = """\
You are an invoice validation specialist. You receive structured invoice
fields (vendor_name, invoice_number, po_number, invoice_amount, invoice_date)
and your job is to flag anomalies before anyone pays this invoice.

Anomaly rules (from the invoice-triage skill):

1. Always call check_duplicate_invoice(invoice_number) first.
   - is_duplicate true → flag "duplicate_invoice"

2. If po_number is present, call lookup_po(po_number):
   - Not found → flag "po_not_found"
   - found, status "closed" → flag "po_already_closed"
   - found, vendor doesn't match → flag "vendor_mismatch"
     (apply suffix normalisation: Inc., LLC, Ltd., Co. are stripped)
   - found, invoice_amount > approved_amount × 1.10 → flag "amount_exceeds_po"
     (report both amounts in the explanation)
   - found, all checks pass → no flag from this PO

3. If po_number is null → flag "missing_po_reference"

4. If any input field is null → flag "extraction_failure"

Output a JSON object:
  "flags": [...],
  "recommendation": "approve" | "hold_for_review",
  "details": "plain English explanation for each flag"

You never approve payments. You never contact vendors. You never
fabricate PO numbers. Your output is a recommendation only.
"""

# Try to use MCP toolset; fall back to direct function imports for local demo.
try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters  # type: ignore
    _tools = [
        MCPToolset(
            connection_params=StdioServerParameters(
                command="python",
                args=["mcp/po_database_mcp.py"],
            )
        )
    ]
except ImportError:
    # Fallback: use in-process functions directly (no MCP protocol)
    import sys
    sys.path.insert(0, str(__file__).replace("agents/validation_agent.py", ""))
    from agents.po_database import check_duplicate_invoice, lookup_po  # type: ignore  # noqa: F401
    _tools = [lookup_po, check_duplicate_invoice]


validation_agent = LlmAgent(
    name="invoice_validation_agent",
    model=Gemini(model="gemini-2.0-flash"),     # Day-1: pro for multi-step reasoning
    instruction=VALIDATION_INSTRUCTION,
    description=(
        "Validates extracted invoice fields against the PO system. "
        "Flags duplicates, missing POs, closed POs, vendor mismatches, "
        "and amount overages. Read-only. Never approves or sends anything."
    ),
    tools=_tools,
)
