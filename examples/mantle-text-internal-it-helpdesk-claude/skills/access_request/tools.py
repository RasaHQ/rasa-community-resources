"""Access-request tools. The guard runs in lib.helpdesk, not in the prompt.

The signed-in employee is project memory that only the session tool writes.
The ticket the engine reads back for confirmation is skill memory that only
``open_access_ticket`` writes (never ``llm_settable``), and only for a ticket
whose exact scope the role's owner has approved. ``grant_access`` checks the
request rules again from the records at the moment of the change. Each value
is one short field: Mantle cuts a memory value at 100 characters in the
prompt without saying so.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import helpdesk as hd

EMPLOYEE_KEY = "project.employee_id"
SELECTION_KEYS = ("selected_ticket_ref", "selected_scope_label")


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hd.HelpdeskService:
    return hd.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


@tool(
    description=(
        "Record an access request for the signed-in employee and check whether the role's owner "
        "has approved exactly that scope. Takes the system and level in the employee's words. "
        "Returns a ticket that is ready to grant, or a ticket awaiting the owner's decision (an "
        "approval request is sent), or candidates to ask about. Changes no access. Call it again "
        "when the employee asks for a different or broader role."
    )
)
async def open_access_ticket(
    role_description: str,
    for_employee: Optional[str] = None,
    business_reason: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Record one access request.

    Args:
        role_description: The system and level in the employee's words, for example viewer on finance reporting.
        for_employee: Only if the employee asks for access for someone else: that person's name as they gave it.
        business_reason: The employee's reason in one short sentence, if they gave one.
    """
    service = _service()
    result = hd.open_access_ticket(service, _get(context, EMPLOYEE_KEY), role_description, for_employee,
                                   business_reason)
    # Only an owner-approved ticket is ever selected for the engine's
    # confirmation question. Anything else clears the selection, so a
    # correction can never leave an earlier ticket confirmed.
    if result.get("status") == "ready_to_grant":
        _set(context, hd.memory_values(service, result["ticket_ref"]))
    else:
        _set(context, {key: "" for key in SELECTION_KEYS})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Grant the access on a ticket that open_access_ticket returned as ready_to_grant. The "
        "engine reads the scope back and asks the employee to confirm first. Adds exactly the "
        "approved role and nothing else, reads the change back from the directory, and returns "
        "the ticket and change references with the scope, its expiry and the unresolved work."
    )
)
async def grant_access(ticket_ref: str, context: ToolContext = None) -> ToolResult:
    """Grant one approved ticket.

    Args:
        ticket_ref: The ticket_ref from open_access_ticket, for example IT-TKT-48213.
    """
    result = hd.grant_access(_service(), _get(context, EMPLOYEE_KEY), _get(context, "selected_ticket_ref"),
                             ticket_ref, conversation_id=_conversation_id())
    if result.get("status") in ("succeeded", "pending", "already_granted"):
        _set(context, {key: "" for key in SELECTION_KEYS})
    return ToolResult(llm_response=result)
