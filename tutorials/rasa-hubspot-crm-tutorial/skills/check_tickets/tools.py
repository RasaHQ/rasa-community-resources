"""LOCAL tool — reading this customer's tickets belongs to this skill alone."""

from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool
from lib.hubspot import CrmError, open_tickets_for


@tool(description="List the support tickets on the identified customer's account.")
async def list_open_tickets(context: ToolContext = None) -> ToolResult:
    """Read the caller's tickets from the CRM."""
    contact_id = context.memory.get("project.contact_id") if context else None
    if not contact_id:
        return ToolResult(llm_response={"ok": False, "error": "not_identified"})

    try:
        tickets = await open_tickets_for(str(contact_id))
    except CrmError as exc:
        return ToolResult(llm_response={"ok": False, "error": exc.reason})

    if context is not None:
        context.memory.set("open_ticket_count", len(tickets))

    return ToolResult(llm_response={"ok": True, "count": len(tickets), "tickets": tickets})
