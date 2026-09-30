"""Orchard Works helpdesk tools shared by the skills: session binding, ticket status, routing.

The helpdesk runs inside the company's chat workspace, where the employee is
already signed in with single sign-on, so the session, not the employee's
words, says whose access this is. The employee id always comes from project
memory, which only ``load_session_employee`` writes. The guard runs in
lib.helpdesk, not in the prompt.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import helpdesk as hd

EMPLOYEE_KEY = "project.employee_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> hd.HelpdeskService:
    return hd.service_for(conversation_id())


def session_employee_id(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(EMPLOYEE_KEY) if context is not None else None) or None


@tool(description="Load the signed-in employee's profile into project memory at session start.")
async def load_session_employee(context: ToolContext = None) -> ToolResult:
    profile = hd.session_profile()
    if context is not None and not context.memory.get(EMPLOYEE_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (Mantle cuts memory values at 100
        # characters in the prompt; see lib.helpdesk.MEMORY_VALUE_LIMIT).
        context.memory.set(EMPLOYEE_KEY, profile["employee_id"])
        context.memory.set("project.employee_first_name", profile["first_name"])
        context.memory.set("project.employee_team", profile["team"])
    public = {k: v for k, v in profile.items() if k != "employee_id"}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "Look up one of the signed-in employee's helpdesk tickets by its reference (IT-TKT-...). "
        "Reports whether it waits for the owner's decision, is ready, is completed, or could not "
        "be confirmed, and reconciles an unconfirmed access change with the directory. Never "
        "grants anything."
    )
)
async def check_ticket_status(ticket_ref: str, context: ToolContext = None) -> ToolResult:
    """Look up a ticket.

    Args:
        ticket_ref: The ticket reference, for example IT-TKT-40117.
    """
    return ToolResult(llm_response=hd.check_ticket_status(service(), session_employee_id(context), ticket_ref))


@tool(
    description=(
        "Route a ticket whose access change the directory cannot confirm, or that needs the "
        "owning team's attention, to the team that owns the role. Returns a routing reference; "
        "decides nothing and changes no access."
    )
)
async def route_access_owner(ticket_ref: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the role's owning team.

    Args:
        ticket_ref: The ticket reference, for example IT-TKT-48213.
        reason: One short sentence, for example directory cannot confirm the change.
    """
    return ToolResult(
        llm_response=hd.route_access_owner(service(), session_employee_id(context), ticket_ref, reason)
    )


@tool(
    description=(
        "Identity recovery: a forgotten password, a lost or new sign-in device, a locked account, "
        "or a request that concerns someone else's account. Hands it to the identity desk and "
        "returns a desk reference. Resets, unlocks and grants nothing."
    )
)
async def route_identity_desk(reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the identity desk.

    Args:
        reason: One short sentence, for example employee lost the phone with their authenticator.
    """
    return ToolResult(llm_response=hd.route_identity_desk(service(), session_employee_id(context), reason))
