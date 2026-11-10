"""Recovery tools. The guard runs in lib.recovery, not in the prompt.

The selected option lives in skill memory that only select_option writes
(never ``llm_settable``), so the option the engine asks the passenger to
confirm is always the one the tool resolved. The model passes the
passenger's words for a booking and an option id copied from a tool result.
No tool takes a seat count, a revision or a fact.

``hold_recovery_option`` sends the passenger its outcome itself through
``ToolContext.send`` (``lib.recovery.TOOL_SENDS_RECEIPT``): the hold id and
expiry, or why no seat is held.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import recovery as hz

PASSENGER_KEY = "project.passenger_id"


# Same helpers as tools/horizon_shared.py. Mantle loads each tool module on
# its own, so skill tools import only from lib/, never from tools/.
def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hz.Disruption:
    return hz.service_for(_conversation_id())


def _passenger(context: Optional[ToolContext]) -> Optional[str]:
    if context is None:
        return hz.SESSION_PASSENGER_ID
    return context.memory.get(PASSENGER_KEY) or None


def _write_selection(context: Optional[ToolContext], result: dict) -> None:
    if context is not None:
        for key, value in hz.selection_memory(result).items():
            context.memory.set(key, value)


@tool(
    description=(
        "List recovery flights for one of the passenger's cancelled bookings at the current incident revision, "
        "with the seat count each shows. A list is information: a seat count is not a hold."
    )
)
async def find_recovery_options(booking: str, context: ToolContext = None) -> ToolResult:
    """Find recovery options.

    Args:
        booking: The passenger's words for the booking, for example my Chicago flight or HT-7Q4M2.
    """
    result = hz.find_recovery_options(_service(), _passenger(context), booking)
    # A new list always clears the previous choice, so a hold can never ride
    # on an option chosen from an older list.
    _write_selection(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record which option from the latest find_recovery_options list the passenger chose, by its option_id. "
        "Holds nothing."
    )
)
async def select_option(option_id: str, context: ToolContext = None) -> ToolResult:
    """Select an option.

    Args:
        option_id: The option_id the passenger chose, for example OPT-ORD-315.
    """
    result = hz.select_option(_service(), _passenger(context), option_id)
    _write_selection(context, result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Place a seat hold on the selected option. The engine asks the passenger to confirm first. The inventory "
        "decides: it returns held with a hold id and expiry, or blocked with the reason nothing is held."
    )
)
async def hold_recovery_option(option_id: str, context: ToolContext = None) -> ToolResult:
    """Hold the selected option.

    Args:
        option_id: The option_id from select_option, for example OPT-ORD-315.
    """
    selected = (context.memory.get("selected_option_id") if context is not None else option_id) or None
    result = hz.hold_recovery_option(_service(), _passenger(context), selected, option_id, _conversation_id())
    if result.get("status") == "blocked":
        # A refused hold cannot be confirmed again; the next choice is new.
        _write_selection(context, {})
    text = hz.customer_receipt("hold_recovery_option", result) if hz.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)
    return ToolResult(llm_response=result)
