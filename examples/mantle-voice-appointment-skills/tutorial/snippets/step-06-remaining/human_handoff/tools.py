"""Tools only the human_handoff skill uses. Auto-discovered — no import_tools."""

from __future__ import annotations

from datetime import datetime

from lib.database import Database, get_user_id, username_from_context
from lib.tool_helpers import set_memory
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="Create a handoff ticket so a member of the clinic team can call back.")
async def create_handoff_ticket(reason: str, context: ToolContext = None) -> ToolResult:
    """Create a handoff ticket.

    Args:
        reason: Why the patient wants to speak to a person.
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    ticket_id = f"HO-{datetime.now().strftime('%H%M%S')}"

    db.run_query(
        """
        INSERT INTO handoff_tickets (user_id, ticket_id, reason, status)
        VALUES (?, ?, ?, 'open')
        """,
        (user_id, ticket_id, reason),
        one_record=False,
    )
    db.commit()

    set_memory(context, "handoff_created", True)
    set_memory(context, "handoff_ticket_id", ticket_id)

    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "eta_minutes": 10,
        }
    )
