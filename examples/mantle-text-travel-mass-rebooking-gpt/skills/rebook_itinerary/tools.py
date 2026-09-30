"""Rebooking tools. The guard runs in lib.rebooking, not in the prompt.

The hold the engine asks the passenger to confirm lives in skill memory that
only these tools write (never ``llm_settable``): hold_recovery_option and
resume_hold set it; release_hold and every commit outcome clear it.
commit_rebooking is withheld from the model while no hold is set, and the tool
itself checks that the hold it is given is that confirmed hold and that it has
not expired on the fixture clock. Each memory value is one short field:
Mantle cuts a memory value at 100 characters in the prompt without saying so.

When ``lib.rebooking.TOOL_SENDS_RECEIPT`` is on, commit_rebooking sends the
passenger its outcome itself through ``ToolContext.send``: the replacement
reference, or the hold expiry with what is unresolved, or why nothing was
booked. The model's reply comes after it, whatever the model does.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import rebooking as rb

PASSENGER_KEY = "project.passenger_id"


# The same helpers as tools/horizon_disruption.py. Skill tool modules import
# lib/, not each other, so each module carries its own copy.
def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> rb.RebookingService:
    return rb.service_for(_conversation_id())


def _passenger(context: Optional[ToolContext]) -> Optional[str]:
    if context is None:
        return rb.SESSION_PASSENGER_ID
    return context.memory.get(PASSENGER_KEY) or None


def _messages(context: Optional[ToolContext]) -> list[str]:
    return rb.passenger_messages(context.events) if context is not None else []


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set_held(context: Optional[ToolContext], values: dict[str, str]) -> None:
    if context is None:
        return
    for key in rb.HELD_KEYS:
        context.memory.set(key, values.get(key, ""))


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = rb.customer_receipt(tool_name, result) if rb.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Search replacement flights for the passenger's disruption case. Each option says whether it meets the "
        "case's constraints (destination, arrival in time for the onward flight, an accessible connection if "
        "needed). Results are offers, not holds."
    )
)
async def search_recovery_options(
    case_reference: str, accessible_connection: bool = False, context: ToolContext = None
) -> ToolResult:
    """Search recovery options.

    Args:
        case_reference: The passenger's disruption case, for example HT-DC-40117.
        accessible_connection: True when the passenger needs a step-free, accessible connection (wheelchair, no stairs).
    """
    return ToolResult(llm_response=rb.search_options(
        _service(), _passenger(context), case_reference, _messages(context), accessible_connection))


@tool(
    description=(
        "Hold one seat on a recovery option for the passenger's case until a stated time. One hold at a time. A "
        "hold reserves capacity; it is not a rebooking. Returns a hold_id and the expiry, or why nothing was held."
    )
)
async def hold_recovery_option(
    case_reference: str, option_id: str, accessible_connection: bool = False, context: ToolContext = None
) -> ToolResult:
    """Hold a recovery option.

    Args:
        case_reference: The passenger's disruption case, for example HT-DC-40117.
        option_id: The option_id from search_recovery_options, for example RB-1303.
        accessible_connection: True when the passenger needs a step-free, accessible connection.
    """
    result = rb.hold_option(_service(), _passenger(context), case_reference, option_id, _messages(context),
                            _conversation_id(), accessible_connection)
    if result["status"] == "held":
        # A new hold always replaces what the confirmation will read, so the
        # passenger confirms the current option and the current expiry.
        _set_held(context, rb.held_memory(result))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pick up a hold the passenger made earlier outside this chat (for example in the app), by its hold_id "
        "(HT-RH-...). Works only if that hold is still active and unexpired."
    )
)
async def resume_hold(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Resume an earlier hold.

    Args:
        hold_id: The hold id the passenger gave, for example HT-RH-7710.
    """
    result = rb.resume_hold(_service(), _passenger(context), hold_id, _messages(context))
    if result["status"] == "held":
        _set_held(context, rb.held_memory(result))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Release an active hold without rebooking: its seat goes back for other passengers. Use when the "
        "passenger switches option, the held option does not meet a new requirement, or they no longer want it."
    )
)
async def release_hold(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Release a hold.

    Args:
        hold_id: The hold_id from hold_recovery_option, for example HT-RH-3F2A1.
    """
    result = rb.release_hold(_service(), _passenger(context), hold_id, len(_messages(context)))
    if result["status"] in ("released", "not_active") and rb.normalise_id(hold_id) == _get(context, "held_hold_id"):
        _set_held(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the one held option to the booking service to rebook the passenger, then read the ticket back. The "
        "engine asks the passenger to confirm first. Returns succeeded with a replacement reference only when the "
        "booking service accepted it; pending when it has not, with the hold expiry."
    )
)
async def commit_rebooking(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Commit a held option.

    Args:
        hold_id: The hold_id from hold_recovery_option.
    """
    result = rb.commit_rebooking(_service(), _passenger(context), _get(context, "held_hold_id"), hold_id,
                                 _messages(context), _conversation_id())
    if not result.get("replay") and (
        result.get("effects") == 1 or rb.normalise_id(hold_id) == _get(context, "held_hold_id")
    ):
        # Every outcome for the confirmed hold ends its confirmation: committed,
        # pending (the booking service owns it now), expired or released. A
        # wrong hold id leaves the confirmed hold alone.
        _set_held(context, {})
    await _send_receipt(context, "commit_rebooking", result)
    return ToolResult(llm_response=result)
