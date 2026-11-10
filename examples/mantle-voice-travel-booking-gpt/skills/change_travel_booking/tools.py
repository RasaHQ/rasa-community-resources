"""Journey-change tools. The guard runs in lib.journeys, not in the prompt.

There is no tool that changes one flight on its own: ``apply_journey_change``
checks every service linked to the segment, changes the segment, re-points the
services and compares their identifiers with the new times before it says
anything is done.

The signed-in traveller is project memory that only the session tool writes.
The draft change (booking, option, the segment as it was, the linked services
and the two read-back labels) is skill memory that only
``prepare_journey_change`` writes (never ``llm_settable``), so what the engine
reads back for confirmation is what the tools checked.

When ``lib.journeys.TOOL_SENDS_RECEIPT`` is on, ``apply_journey_change`` sends
the caller the receipt itself through ``ToolContext.send``: each linked
service's state, the change reference, and on a partial change the unresolved
service and the travel-desk reference. On voice the tool waits while that
receipt is spoken, which is why ``agent.yml`` sets ``tool_timeout: 30``.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import UserUttered

from lib import journeys as hj

TRAVELLER_KEY = "project.traveller_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hj.JourneyService:
    return hj.service_for(_conversation_id())


def _traveller(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(TRAVELLER_KEY) if context is not None else None) or None


def _caller_texts(context: Optional[ToolContext]) -> list[str]:
    """The caller's own messages, as speech-to-text heard them. /session_start is not words."""
    if context is None:
        return []
    return [e.text or "" for e in context.events
            if isinstance(e, UserUttered) and not (e.text or "").startswith("/")]


def _memory(context: Optional[ToolContext]) -> dict:
    return {key: (context.memory.get(key) if context is not None else None) or None for key in hj.MEMORY_KEYS}


def _set_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key in hj.MEMORY_KEYS:
        context.memory.set(key, values.get(key, ""))


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = hj.customer_receipt(tool_name, result) if hj.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)
        result["receipt_sent_to_caller"] = True


@tool(
    description=(
        "Look up one of the signed-in traveller's bookings: its flight segments (flown or open) and the "
        "services linked to them. Takes the booking reference or the trip's destination city; empty lists "
        "the traveller's trips. Flight delays are not here: use check_flight_status."
    )
)
async def look_up_trip(booking: str = "", context: ToolContext = None) -> ToolResult:
    """Look up a booking.

    Args:
        booking: The booking reference the caller gave, for example HZ4R8N, or the trip's city, for example Lisbon.
    """
    return ToolResult(llm_response=hj.look_up_trip(_service(), _traveller(context), booking, _caller_texts(context)))


@tool(
    description=(
        "Read a flight's operational status (on time, delayed) for a date. This is a separate fact from the "
        "booking: it changes nothing and moves no connection or service."
    )
)
async def check_flight_status(flight_number: str, date: str = "", context: ToolContext = None) -> ToolResult:
    """Flight status.

    Args:
        flight_number: The flight, for example HZ 215.
        date: The flight date, for example 2026-10-24. Empty means the date on the traveller's booking.
    """
    return ToolResult(llm_response=hj.check_flight_status(_service(), _traveller(context), flight_number, date))


@tool(
    description=(
        "Resolve which flight segment of a booking the caller wants to change, and list the replacement "
        "flights for it with their option ids. Returns needs_segment when the words fit more than one "
        "open segment, and not_changeable for a flown one. Changes nothing."
    )
)
async def find_change_options(booking: str, segment: str, context: ToolContext = None) -> ToolResult:
    """Find change options.

    Args:
        booking: The booking reference, for example HZ4R8N, or the trip's city.
        segment: The caller's words for the flight to change, for example "Lisbon to Boston on October 24" or "HZ 215".
    """
    return ToolResult(llm_response=hj.find_change_options(_service(), _traveller(context), booking, segment,
                                                           _caller_texts(context)))


@tool(
    description=(
        "Prepare a change of one segment to a replacement option from find_change_options, and find every "
        "service linked to it. Sets up the confirmation; changes nothing. A new call replaces the previous "
        "draft."
    )
)
async def prepare_journey_change(booking: str, option_id: str, context: ToolContext = None) -> ToolResult:
    """Prepare a journey change.

    Args:
        booking: The booking reference, for example HZ4R8N.
        option_id: The option_id from find_change_options, for example HZ4R8N-S3-A.
    """
    result, memory = hj.prepare_journey_change(_service(), _traveller(context), booking, option_id,
                                               _caller_texts(context))
    if memory:
        _set_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Make the prepared journey change: check every linked service, change the segment, move the linked "
        "services and reconcile them. The engine reads the change and the linked services back and asks the "
        "caller first. If a linked service is left unresolved, the booking is frozen for the travel desk."
    )
)
async def apply_journey_change(booking: str, context: ToolContext = None) -> ToolResult:
    """Apply the prepared change.

    Args:
        booking: The booking reference the change was prepared for, for example HZ4R8N.
    """
    result = hj.apply_journey_change(_service(), _traveller(context), _memory(context), booking,
                                     _caller_texts(context))
    if result["status"] in ("succeeded", "pending") or result.get("reason") == "connection_not_checked":
        _set_memory(context, {})
    await _send_receipt(context, "apply_journey_change", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Discard the prepared change when the caller does not want it, or before preparing a different "
        "segment. Changes nothing on the booking."
    )
)
async def discard_journey_change(context: ToolContext = None) -> ToolResult:
    """Discard the draft change."""
    result = hj.discard_journey_change(_memory(context))
    _set_memory(context, {})
    return ToolResult(llm_response=result)
