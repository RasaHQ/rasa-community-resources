"""Escalation skill tools â€” local to skills/escalation/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.tool_helpers import active_tech_id, tech_display_name


@tool(description="Raise an escalation ticket to dispatch.")
async def raise_escalation(
    reason: str, context: ToolContext = None
) -> ToolResult:
    """Create a dispatch escalation ticket.

    Args:
        reason: Short reason for the escalation.
    """
    tech_id = active_tech_id(context)
    display_name = tech_display_name(context) or tech_id

    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_ref": "E999",
            "tech_id": tech_id,
            "display_name": display_name,
            "reason": str(reason).strip(),
            "status": "open",
        }
    )
