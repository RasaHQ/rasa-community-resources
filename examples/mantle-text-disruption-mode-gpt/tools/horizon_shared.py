"""Horizon Travel tools shared by the disruption skills.

The chat runs for a signed-in passenger, so the session, not the passenger's
words, says whose bookings these are. The passenger id always comes from
project memory, which only ``load_session_passenger`` writes. The model
supplies the passenger's words for a booking and a hold id copied from a tool
result; never a passenger id, a fact, a seat count or an outcome.

``release_hold`` and ``join_recovery_queue`` send the passenger their own
outcome through ``ToolContext.send`` (``lib.recovery.TOOL_SENDS_RECEIPT``).
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import recovery as hz

PASSENGER_KEY = "project.passenger_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> hz.Disruption:
    return hz.service_for(conversation_id())


def session_passenger_id(context: Optional[ToolContext]) -> Optional[str]:
    if context is None:
        return hz.SESSION_PASSENGER_ID
    return context.memory.get(PASSENGER_KEY) or None


async def send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = hz.customer_receipt(tool_name, result) if hz.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the signed-in passenger's profile into project memory at session start.")
async def load_session_passenger(context: ToolContext = None) -> ToolResult:
    profile = hz.session_profile()
    if context is not None and not context.memory.get(PASSENGER_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # One short field per value (Mantle cuts memory values at 100
        # characters in the prompt; see lib.recovery.MEMORY_VALUE_LIMIT).
        context.memory.set(PASSENGER_KEY, profile["passenger_id"])
        context.memory.set("project.passenger_first_name", profile["first_name"])
        context.memory.set("project.affected_trips", profile["affected_trips"])
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"],
                                    "affected_trips": profile["affected_trips"]})


@tool(
    description=(
        "Read the storm incident's current status and revision, and optionally one booking's flight status, "
        "active hold and queue entry. Information only: it never holds or promises a seat."
    )
)
async def get_incident_status(booking: Optional[str] = None, context: ToolContext = None) -> ToolResult:
    """Read the incident status.

    Args:
        booking: Optional. The passenger's words for one booking, for example my Chicago flight or HT-7Q4M2.
    """
    return ToolResult(llm_response=hz.incident_status(service(), session_passenger_id(context), booking))


@tool(
    description=(
        "Look up a seat hold by its hold id (HT-HLD-...): active with its expiry, expired or released. "
        "Use it for a hold the passenger already has; it never places a hold."
    )
)
async def check_hold(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Check a hold.

    Args:
        hold_id: The hold id, for example HT-HLD-4K7M.
    """
    return ToolResult(llm_response=hz.check_hold(service(), session_passenger_id(context), hold_id))


@tool(
    description=(
        "Release a seat hold the passenger has rejected, by its hold id. The seat is no longer held. "
        "Call it only when the passenger says they do not want the held option."
    )
)
async def release_hold(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Release a hold.

    Args:
        hold_id: The hold id from hold_recovery_option or check_hold, for example HT-HLD-4K7M.
    """
    result = hz.release_hold(service(), session_passenger_id(context), hold_id)
    await send_receipt(context, "release_hold", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Put one of the passenger's cancelled bookings in the recovery queue. Returns a queue reference and "
        "position: an honest queued status, not a seat and not a confirmed journey."
    )
)
async def join_recovery_queue(booking: str, context: ToolContext = None) -> ToolResult:
    """Join the recovery queue.

    Args:
        booking: The passenger's words for the booking, for example my Washington flight or HT-3H6W4.
    """
    result = hz.join_recovery_queue(service(), session_passenger_id(context), booking, conversation_id())
    await send_receipt(context, "join_recovery_queue", result)
    return ToolResult(llm_response=result)
