"""Return-and-exchange tools. The guard runs in lib.returns, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The selected item and the recorded choice are skill memory that only these
tools write (never ``llm_settable``), so the request the engine reads back for
confirmation is always the item ``find_order_item`` resolved and the choice
``choose_resolution`` recorded. Each value is one short field: Mantle cuts a
memory value at 100 characters in the prompt without saying so.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import UserUttered

from lib import returns as wr

CUSTOMER_KEY = "project.customer_id"
CHOICE_KEYS = ("selected_resolution", "selected_resolution_label", "selected_replacement_ref")


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> wr.ReturnsService:
    return wr.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


def _user_texts(context: Optional[ToolContext]) -> list[str]:
    if context is None:
        return []
    return [e.text or "" for e in context.events if isinstance(e, UserUttered)]


@tool(
    description=(
        "Find the item the customer wants to return or exchange, on one of their own "
        "orders, from the order number (if they gave one) and the item in their words. "
        "Returns the item_ref and whether it is eligible, or candidates to ask about."
    )
)
async def find_order_item(
    item_description: str,
    order_number: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Find one item.

    Args:
        item_description: The item in the customer's words, for example the linen shirt.
        order_number: The order number if the customer gave one, for example WS-20611.
    """
    service = _service()
    result = wr.find_order_item(service, _get(context, CUSTOMER_KEY), order_number, item_description)
    # A new lookup always replaces the old selection and clears the old choice,
    # so a correction can never leave an earlier item or resolution confirmed.
    selected = result.get("item_ref", "") if result.get("eligible") is True else ""
    _set(context, {
        "selected_item_ref": selected,
        "selected_item_label": wr.memory_values(service, selected)["selected_item_label"] if selected else "",
        **{key: "" for key in CHOICE_KEYS},
    })
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the customer's choice for the selected item: return or exchange, and for "
        "an exchange the replacement they asked for. Only record what the customer said "
        "in their own words; never choose for them. Call it again when they change their "
        "mind."
    )
)
async def choose_resolution(
    item_ref: str,
    resolution: str,
    replacement: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Record return or exchange.

    Args:
        item_ref: The item_ref from find_order_item, for example WS-20611-1.
        resolution: return or exchange, as the customer chose.
        replacement: For an exchange, the replacement in the customer's words, for example size M.
    """
    service = _service()
    result = wr.choose_resolution(
        service,
        _get(context, CUSTOMER_KEY),
        _get(context, "selected_item_ref"),
        item_ref,
        resolution,
        replacement,
        _user_texts(context),
    )
    if result["status"] == "recorded":
        values = wr.memory_values(service, result["item_ref"], result)
        _set(context, {k: values[k] for k in CHOICE_KEYS})
    else:
        # A refused choice clears the old one: the engine must never read back a
        # resolution the customer has since moved away from.
        _set(context, {key: "" for key in CHOICE_KEYS})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Request the return authorization or exchange for the selected item and the "
        "recorded choice. The engine reads the request back and asks the customer to "
        "confirm first. Returns an RMA reference, a label reference and the next stage; "
        "it never issues or promises a refund."
    )
)
async def submit_return_request(item_ref: str, resolution: str, context: ToolContext = None) -> ToolResult:
    """Submit one return or exchange request.

    Args:
        item_ref: The item_ref from find_order_item, for example WS-20611-1.
        resolution: return or exchange, the choice recorded by choose_resolution.
    """
    memory = {key: _get(context, key) for key in ("selected_item_ref", *CHOICE_KEYS)}
    result = wr.submit_return_request(
        _service(),
        _get(context, CUSTOMER_KEY),
        memory,
        item_ref,
        resolution,
        _user_texts(context),
        conversation_id=_conversation_id(),
    )
    return ToolResult(llm_response=result)
