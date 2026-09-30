"""Advisor-booking tools. The guard runs in lib.appointments, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The held slot is skill memory that only these tools write (never
``llm_settable``), so the booking the engine reads back for confirmation is
always the slot ``hold_slot`` held. The customer's stated purpose, channel and
access needs are read from their own messages in the tracker (on a voice call,
what speech-to-text heard), never from the model's arguments alone.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import UserUttered

from lib import appointments as na

CUSTOMER_KEY = "project.customer_id"
HOLD_KEYS = ("held_slot_id", "held_team_label", "held_purpose_label", "held_slot_label")


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> na.SchedulingService:
    return na.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set_hold(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key in HOLD_KEYS:
        context.memory.set(key, values.get(key, ""))


def _user_texts(context: Optional[ToolContext]) -> list[str]:
    """The customer's own messages. /session_start and other engine intents are not words."""
    if context is None:
        return []
    return [e.text or "" for e in context.events
            if isinstance(e, UserUttered) and not (e.text or "").startswith("/")]


def _customer(context: Optional[ToolContext]) -> Optional[str]:
    return _get(context, CUSTOMER_KEY)


@tool(
    description=(
        "Find proposed advisor appointment times from teams that can handle the customer's "
        "stated purpose. Filters: meeting channel (branch, phone or video), branch name, day "
        "and part of day. Proposals reserve nothing. When no capable team fits, returns "
        "alternatives and whether a callback is available."
    )
)
async def find_advisor_slots(
    purpose: str,
    channel: Optional[str] = None,
    branch: Optional[str] = None,
    day: Optional[str] = None,
    part_of_day: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Search the advisor diary.

    Args:
        purpose: What the customer said the appointment is about: mortgage, investments, business_banking or everyday_banking.
        channel: branch, phone or video, only if the customer said how they want to meet.
        branch: Branch name as the customer said it, only for a branch visit, for example Kingsmere.
        day: A weekday or a date the customer asked for, for example Thursday or 2026-10-08.
        part_of_day: morning or afternoon, only if the customer said.
    """
    result = na.find_advisor_slots(_service(), _customer(context), _user_texts(context), purpose, channel,
                                   branch, day, part_of_day)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Hold one proposed slot the customer picked, so it is reserved for this call while "
        "they confirm. Checks that the team can handle their stated purpose and that the "
        "meeting channel and access fit. Only one slot can be held at a time."
    )
)
async def hold_slot(slot_id: str, purpose: str, context: ToolContext = None) -> ToolResult:
    """Hold one slot.

    Args:
        slot_id: The slot_id from find_advisor_slots, for example SLT-MTG-P0814.
        purpose: The customer's stated purpose: mortgage, investments, business_banking or everyday_banking.
    """
    service = _service()
    result = na.hold_slot(service, _customer(context), _user_texts(context), slot_id, purpose)
    if result["status"] == "held":
        _set_hold(context, na.memory_values(service, result["slot"]["slot_id"], result["purpose"]))
    elif not service.active_hold():
        _set_hold(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Release the slot held on this call, when it no longer fits what the customer needs "
        "(another channel, another purpose, step-free access, another time)."
    )
)
async def release_hold(slot_id: str, context: ToolContext = None) -> ToolResult:
    """Release a hold.

    Args:
        slot_id: The slot_id of the held slot.
    """
    result = na.release_hold(_service(), slot_id)
    if result["status"] == "released":
        _set_hold(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Book the held slot. The engine reads the team, purpose, channel and time back and "
        "asks the customer to confirm first. Returns a booking reference naming the channel, "
        "purpose and confirmed time. It gives no financial advice."
    )
)
async def book_appointment(slot_id: str, context: ToolContext = None) -> ToolResult:
    """Book one held slot.

    Args:
        slot_id: The slot_id of the held slot, for example SLT-MTG-P0814.
    """
    service = _service()
    result = na.book_appointment(service, _customer(context), _user_texts(context), _get(context, "held_slot_id"),
                                 slot_id, conversation_id=_conversation_id())
    if result["status"] == "succeeded" or result.get("detail") == "hold_lapsed":
        _set_hold(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Ask a team that can handle the customer's stated purpose to phone them to arrange "
        "an appointment, when no proposed time suits. Reserves no slot. Returns a callback "
        "reference."
    )
)
async def request_callback(purpose: str, preferred_time: Optional[str] = None,
                           context: ToolContext = None) -> ToolResult:
    """Request a callback.

    Args:
        purpose: The customer's stated purpose: mortgage, investments, business_banking or everyday_banking.
        preferred_time: When the customer would like the call, in their words, if they said.
    """
    result = na.request_callback(_service(), _customer(context), _user_texts(context), purpose, preferred_time,
                                 conversation_id=_conversation_id())
    return ToolResult(llm_response=result)
