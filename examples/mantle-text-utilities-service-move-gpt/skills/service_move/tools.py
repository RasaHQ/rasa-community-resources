"""Move tools. The guard runs in lib.moves, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The draft and its read-back values are skill memory that only these tools
write (never ``llm_settable``), so the move the engine reads back for
confirmation is always the draft the tools hold. Each value is one short
field: Mantle cuts a memory value at 100 characters in the prompt without
saying so.

No tool takes a date as a value it trusts, a premises id or a fact. The model
passes the customer's words for the service they are leaving, the address
they are moving to and each date; the tools resolve the premises from the
register and read the day from the words, and a day the customer never said
is refused. No tool closes a service.

When ``lib.moves.TOOL_SENDS_RECEIPT`` is on, ``submit_move_order`` sends the
customer its outcome itself through ``ToolContext.send``: the move-order
reference with both dates, or "not confirmed, your supply stays on".
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import moves as ag
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ag.MoveService:
    return ag.service_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> str:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or ag.SESSION_CUSTOMER_ID


def _conversation(context: Optional[ToolContext]) -> ag.Conversation:
    return conversation_from_events(context.events) if context is not None else ag.Conversation()


def _write_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = ag.customer_receipt(tool_name, result) if ag.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Open a draft move for the signed-in customer: the service they are leaving, the address they are moving "
        "to, and the move-out and move-in days, each in the customer's own words. The tool finds the premises in "
        "Amber Grid's register and reads the exact days. A draft schedules nothing and changes no service."
    )
)
async def start_move_draft(
    moving_out_of: str,
    moving_to: str,
    move_out_date: str,
    move_in_date: str,
    context: ToolContext = None,
) -> ToolResult:
    """Open a draft move.

    Args:
        moving_out_of: The service they are leaving, as they named it, for example 12 Wren Street or the flat.
        moving_to: The new address as the customer gave it, for example Flat 5, 41 Quarry Lane, Millbrook.
        move_out_date: The last day at the current address as the customer said it, for example 24 October.
        move_in_date: The first day at the new address as the customer said it, for example 24 October.
    """
    service = _service()
    result, memory = ag.start_move_draft(
        service, _customer(context), _conversation(context), _conversation_id(),
        moving_out_of, moving_to, move_out_date, move_in_date,
    )
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Change a draft move: the new address, the move-out day or the move-in day, in the customer's words. Any "
        "change makes a new version that the customer must confirm again, both sides and both dates. Also changes "
        "a move order that was already scheduled; nothing changes until the customer confirms."
    )
)
async def update_move_draft(
    draft_id: str,
    moving_to: Optional[str] = None,
    move_out_date: Optional[str] = None,
    move_in_date: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Change a draft move.

    Args:
        draft_id: The draft_id from start_move_draft, for example AG-MVD-3A9C1.
        moving_to: A corrected new address, in the customer's words.
        move_out_date: A corrected move-out day, as the customer said it.
        move_in_date: A corrected move-in day, as the customer said it.
    """
    service = _service()
    result, memory = ag.update_move_draft(
        service, _customer(context), _conversation(context), draft_id, moving_to, move_out_date, move_in_date,
    )
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the draft move to Amber Grid's move-order system. The engine reads both sides and both dates back and "
        "asks the customer first. Returns a move-order reference only when the order system acknowledges it and its "
        "read-back matches; otherwise the move is pending and the current service stays on."
    )
)
async def submit_move_order(draft_id: str, context: ToolContext = None) -> ToolResult:
    """Submit one confirmed draft move.

    Args:
        draft_id: The draft_id from start_move_draft.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in ag.MEMORY_KEYS}
    result = ag.submit_move_order(
        _service(), _customer(context), memory, _conversation(context), draft_id, _conversation_id(),
    )
    await _send_receipt(context, "submit_move_order", result)
    return ToolResult(llm_response=result)
