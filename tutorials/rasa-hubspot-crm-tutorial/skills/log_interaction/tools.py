"""LOCAL tool — writing to the customer's timeline belongs to this skill."""

from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool
from lib.hubspot import CrmError, log_note


@tool(description="Save a short summary of this conversation to the customer's CRM timeline.")
async def add_timeline_note(summary: str, context: ToolContext = None) -> ToolResult:
    """Write a note onto the customer's CRM record.

    Args:
        summary: One or two sentences describing what the caller wanted.
    """
    contact_id = context.memory.get("project.contact_id") if context else None
    if not contact_id:
        return ToolResult(llm_response={"ok": False, "error": "not_identified"})

    try:
        note_id = await log_note(str(contact_id), summary)
    except CrmError as exc:
        # A failed write is the dangerous one: never let the agent claim it
        # saved something that is not there.
        return ToolResult(llm_response={"ok": False, "error": exc.reason})

    if context is not None:
        context.memory.set("last_note_id", note_id)

    return ToolResult(llm_response={"ok": True, "note_id": note_id})
