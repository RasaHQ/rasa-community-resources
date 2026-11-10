"""Access-reset tools. The guard runs in lib.access, not in the prompt.

The pending request (whose access, which change) is skill memory that only
``prepare_access_request`` writes (never ``llm_settable``), so the request the
engine reads back in its confirmation question is always the one the tool
resolved, and ``start_verification`` refuses any other. The model passes a
spoken name, an action word and references copied from tool results.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import access as ow


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ow.IdentityService:
    return ow.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


@tool(
    description=(
        "Find the Orchard Works employee whose access the caller wants changed, from the "
        "full name they said, and record the one change they asked for: unlock_account, "
        "reset_password or move_authenticator. Returns a request_ref. A name match is not "
        "permission to change anything."
    )
)
async def prepare_access_request(full_name: str, action: str, context: ToolContext = None) -> ToolResult:
    """Prepare one access request.

    Args:
        full_name: The first and last name of the employee whose access should change, as the caller said it.
        action: unlock_account, reset_password or move_authenticator.
    """
    result = ow.prepare_access_request(_service(), full_name, action)
    if context is not None:
        # A new request always replaces the pending one, so a correction can
        # never leave an earlier subject or action waiting for confirmation.
        prepared = result["status"] == "prepared"
        context.memory.set("pending_request_ref", result["request_ref"] if prepared else "")
        context.memory.set("pending_subject_label", result["employee"] if prepared else "")
        context.memory.set("pending_action_label", result["action_label"] if prepared else "")
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send a fresh approval prompt for the prepared request to the Orchard Works "
        "Authenticator on the phone registered to that employee. The engine asks the caller "
        "first. Returns a challenge_ref."
    )
)
async def start_verification(request_ref: str, context: ToolContext = None) -> ToolResult:
    """Start step-up verification for one request.

    Args:
        request_ref: The request_ref from prepare_access_request, for example OW-REQ-418266.
    """
    return ToolResult(
        llm_response=ow.start_verification(_service(), request_ref, _get(context, "pending_request_ref"))
    )


@tool(
    description=(
        "Read what the employee's registered device answered to an approval prompt: approved, "
        "waiting, denied or timed_out. Call it when the caller says they approved."
    )
)
async def check_verification(challenge_ref: str, context: ToolContext = None) -> ToolResult:
    """Check a verification challenge.

    Args:
        challenge_ref: The challenge_ref from start_verification.
    """
    return ToolResult(llm_response=ow.check_verification(_service(), challenge_ref))


@tool(
    description=(
        "Make the one access change a verified challenge authorizes, for the employee it was "
        "sent to. Refuses unless the challenge was approved, is unused, and matches both the "
        "employee and the action. Returns an authorization reference."
    )
)
async def change_access(challenge_ref: str, employee_ref: str, action: str, context: ToolContext = None) -> ToolResult:
    """Change one employee's access.

    Args:
        challenge_ref: The approved challenge_ref.
        employee_ref: The employee_ref from prepare_access_request, for example OW-EMP-1042.
        action: unlock_account, reset_password or move_authenticator.
    """
    return ToolResult(llm_response=ow.change_access(_service(), challenge_ref, employee_ref, action))


@tool(
    description=(
        "Cancel a verification the caller no longer wants. The challenge stops working and "
        "no access changes."
    )
)
async def cancel_verification(challenge_ref: str, context: ToolContext = None) -> ToolResult:
    """Cancel a verification challenge.

    Args:
        challenge_ref: The challenge_ref to cancel.
    """
    return ToolResult(llm_response=ow.cancel_verification(_service(), challenge_ref))


@tool(
    description=(
        "Route the request to the Orchard Works identity desk when verification timed out, was "
        "denied, or cannot be done on this call. Invalidates the open challenge you name. "
        "Returns a desk reference."
    )
)
async def route_identity_desk(
    reason: str,
    employee_ref: Optional[str] = None,
    challenge_ref: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Route to the identity desk.

    Args:
        reason: One short sentence, for example approval prompt timed out.
        employee_ref: The employee_ref, if the request got that far.
        challenge_ref: The open or failed challenge_ref, if there is one.
    """
    return ToolResult(llm_response=ow.route_identity_desk(_service(), reason, employee_ref, challenge_ref))
