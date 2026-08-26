"""Tools local to the human_handoff skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from datetime import datetime

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult


@tool(description="Create a human handoff ticket for a live agent.")
async def create_handoff_ticket(reason: str, context: ToolContext = None) -> ToolResult:
    """Create a handoff ticket.

    Args:
        reason: Why the customer wants a human agent.
    """
    ticket_id = f"HO-{datetime.utcnow().strftime('%H%M%S')}"
    if context is not None:
        context.memory.set("handoff_created", True)
        context.memory.set("handoff_ticket_id", ticket_id)
    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "eta_minutes": 5,
        }
    )
