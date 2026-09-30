"""Retention tools. The guard runs in lib.retention, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The offer under consideration is skill memory that only get_retention_offer
writes (never ``llm_settable``), so the offer the engine reads back is always
one the catalogue authorizes. Each value is one short field: Mantle cuts a
memory value at 100 characters in the prompt without saying so.

No tool takes a price, a discount, a term, a fact or an outcome. The model
passes the customer's words for the service and an offer id copied from a
tool result. The cancellation request is recorded whatever happens to an
offer; it is a request, not the closure of the account.

When ``lib.retention.TOOL_SENDS_RECEIPT`` is on, record_cancellation_request
and accept_retention_offer send the customer their reference themselves
through ``ToolContext.send``.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import retention as jm
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _desk() -> jm.RetentionDesk:
    return jm.desk_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> str:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or jm.SESSION_CUSTOMER_ID


def _conversation(context: Optional[ToolContext]) -> jm.Conversation:
    return conversation_from_events(context.events) if context is not None else jm.Conversation()


def _write_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = jm.customer_receipt(tool_name, result) if jm.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Record the customer's request to cancel one of their services, in their own words. Always available: no "
        "offer gates it. It records a cancellation request with a reference; it does not close the account."
    )
)
async def record_cancellation_request(service: str, context: ToolContext = None) -> ToolResult:
    """Record a cancellation request.

    Args:
        service: The service to cancel as the customer named it, for example my mobile or the home fibre.
    """
    result = jm.record_cancellation_request(_desk(), _customer(context), _conversation_id(), service)
    await _send_receipt(context, "record_cancellation_request", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Ask Juniper Mobile's offer catalogue for the one authorized retention offer on a service. Returns it only "
        "when the customer has not refused offers, their contact permission is current and the way out is open; "
        "otherwise returns blocked and offers nothing. Shows the customer nothing."
    )
)
async def get_retention_offer(service: str, context: ToolContext = None) -> ToolResult:
    """Look up the authorized offer for one service.

    Args:
        service: The service as the customer named it, for example my mobile.
    """
    result, memory = jm.get_retention_offer(_desk(), _customer(context), _conversation(context), _conversation_id(),
                                            service)
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the customer's choice of the authorized offer get_retention_offer returned. The engine first reads "
        "the offer and the way out back and asks which the customer prefers. Records nothing unless every rule holds."
    )
)
async def accept_retention_offer(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Record one accepted offer.

    Args:
        offer_id: The offer_id from get_retention_offer, for example JM-OFR-M12.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in jm.MEMORY_KEYS}
    result, new_memory = jm.accept_retention_offer(_desk(), _customer(context), memory, _conversation(context),
                                                   offer_id, _conversation_id())
    _write_memory(context, new_memory)
    await _send_receipt(context, "accept_retention_offer", result)
    return ToolResult(llm_response=result)
