"""Shared Horizon Travel disruption tools, used by more than one skill.

The passenger id and their disruption case come from project memory, which
load_passenger_profile writes at session start from the signed-in web-chat
session. The model supplies only references copied from the passenger or
from tool results; it never supplies a passenger id, a fact or an outcome.

When ``lib.rebooking.TOOL_SENDS_RECEIPT`` is on, check_rebooking_status and
request_recovery_desk send the passenger their outcome themselves through
``ToolContext.send``, whatever the model says next.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import rebooking as rb

PASSENGER_KEY = "project.passenger_id"


def conversation_id() -> str:
    """The conversation this tool call belongs to, from Mantle's turn context."""
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> rb.RebookingService:
    return rb.service_for(conversation_id())


def session_passenger(context: Optional[ToolContext]) -> Optional[str]:
    """The passenger bound to this session, from trusted project memory."""
    if context is None:
        return rb.SESSION_PASSENGER_ID
    return context.memory.get(PASSENGER_KEY) or None


def messages(context: Optional[ToolContext]) -> list[str]:
    return rb.passenger_messages(context.events) if context is not None else []


async def send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = rb.customer_receipt(tool_name, result) if rb.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the signed-in passenger's profile and disruption case into project memory at session start.")
async def load_passenger_profile(context: ToolContext = None) -> ToolResult:
    profile = rb.passenger_profile(service())
    if context is not None and not context.memory.get(PASSENGER_KEY):
        context.memory.set(PASSENGER_KEY, profile["passenger_id"])
        context.memory.set("project.passenger_first_name", profile["first_name"])
        context.memory.set("project.disruption_case", profile["disruption_case"])
    return ToolResult(llm_response={"ok": True, **profile})


@tool(
    description=(
        "Read the passenger's disruption case: the cancelled flight, the onward flight still booked, the latest "
        "arrival time, requirements, any active or expired hold, and the committed replacement if there is one."
    )
)
async def get_disruption_case(case_reference: str, context: ToolContext = None) -> ToolResult:
    """Read a disruption case.

    Args:
        case_reference: The disruption case, for example HT-DC-40117. The passenger's own case is in memory.
    """
    msgs = messages(context)
    return ToolResult(llm_response=rb.disruption_case(service(), session_passenger(context), case_reference, len(msgs)))


@tool(
    description=(
        "Ask the booking service again about a rebooking that came back pending, by its commit reference "
        "(HT-CM-...). Returns committed with the replacement reference, or still pending with the hold expiry."
    )
)
async def check_rebooking_status(commit_reference: str, context: ToolContext = None) -> ToolResult:
    """Check a pending rebooking.

    Args:
        commit_reference: The commit_reference from commit_rebooking, for example HT-CM-4A1F0.
    """
    msgs = messages(context)
    result = rb.rebooking_status(service(), session_passenger(context), commit_reference, len(msgs))
    await send_receipt(context, "check_rebooking_status", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the passenger's disruption case to the Horizon Travel disruption recovery desk: for a rebooking the "
        "booking service has not accepted, when no usable option is left, or when the passenger wants a constraint "
        "on the case changed. Returns a desk reference."
    )
)
async def request_recovery_desk(case_reference: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route the case to the recovery desk.

    Args:
        case_reference: The disruption case, for example HT-DC-40117.
        reason: One short sentence: why the desk is needed.
    """
    msgs = messages(context)
    result = rb.recovery_desk(service(), session_passenger(context), case_reference, reason, len(msgs))
    await send_receipt(context, "request_recovery_desk", result)
    return ToolResult(llm_response=result)
