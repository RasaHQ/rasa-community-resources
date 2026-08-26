"""Human-handoff skill tools (auto-discovered)."""

from __future__ import annotations

from datetime import datetime

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import DEMO_CUSTOMER_ID, customer_id_from_context


@tool(description="Create a human handoff ticket for a live support agent.")
async def create_support_ticket(reason: str, context: ToolContext = None) -> ToolResult:
    """Create a handoff ticket.

    Args:
        reason: Why the customer wants a human agent.
    """
    ticket_id = f"TEL-{datetime.utcnow().strftime('%H%M%S')}"
    if context is not None:
        context.memory.set("handoff_created", True)
        context.memory.set("handoff_ticket_id", ticket_id)
    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "eta_minutes": 5,
            "customer_id": customer_id_from_context(context) or DEMO_CUSTOMER_ID,
        }
    )
