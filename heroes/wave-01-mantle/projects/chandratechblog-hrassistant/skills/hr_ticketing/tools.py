"""Ticketing tools for the HR assistant."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

TICKETS: dict[str, dict[str, str]] = {
    "HR-10042": {
        "status": "In progress",
        "next_step": "The assigned HR support team is reviewing the request.",
    },
    "HR-10043": {
        "status": "Waiting for employee information",
        "next_step": "Reply through the approved HR channel with the requested details.",
    },
    "new_ticket": {
        "ticket_number": "HR-NEW-DEMO",
        "status": "Received",
        "next_step": "The request will be routed to the appropriate HR support team.",
    },
}


def _load_tickets() -> dict[str, dict[str, str]]:
    """Return the in-module demo ticket catalog."""
    return TICKETS


@tool(description="Create an HR support ticket after the employee reviewed and confirmed the details.")
async def create_ticket(
    category: str,
    subject: str,
    description: str,
    priority: str,
    context: ToolContext = None,
) -> ToolResult:
    """Return the configured demo response for a new HR ticket."""
    ticket = _load_tickets()["new_ticket"]
    if context is not None:
        context.memory.set("ticket_number", ticket["ticket_number"])
    return ToolResult(
        llm_response={
            "ok": True,
            "demo": True,
            "ticket_number": ticket["ticket_number"],
            "status": ticket["status"],
            "next_step": ticket["next_step"],
        }
    )


@tool(description="Look up the current status and next step for an existing HR ticket number.")
async def track_ticket(ticket_number: str, context: ToolContext = None) -> ToolResult:
    """Return a ticket record from the JSON catalog or a not-found response."""
    ticket = _load_tickets().get(ticket_number.upper())
    if ticket is None:
        return ToolResult(llm_response={"ok": False, "found": False, "ticket_number": ticket_number})
    return ToolResult(
        llm_response={
            "ok": True,
            "found": True,
            "demo": True,
            "ticket_number": ticket_number.upper(),
            **ticket,
        }
    )
