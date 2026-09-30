"""Block-card tools. The guard runs in lib.northgate, not in the prompt.

The verified customer id and the selected card live in memory that only these
tools write (never ``llm_settable``). The model passes a name, a date of
birth, a card ending and a card reference copied from ``select_card``.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import northgate as ng

CUSTOMER_KEY = "project.verified_customer_id"
FIRST_NAME_KEY = "project.caller_first_name"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ng.CardService:
    return ng.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


@tool(
    description=(
        "Verify the caller from their full name and date of birth before any card "
        "is selected or blocked. Pass the date as YYYY-MM-DD."
    )
)
async def verify_caller(full_name: str, date_of_birth: str, context: ToolContext = None) -> ToolResult:
    """Verify the caller.

    Args:
        full_name: The caller's first and last name as they said it.
        date_of_birth: Date of birth as YYYY-MM-DD, for example 1990-07-21.
    """
    result = ng.verify_caller(_service(), full_name, date_of_birth)
    if context is not None and result["status"] == "verified":
        # Mantle project memory is write-once: a field that is set cannot be
        # overwritten. So a failed attempt writes nothing (the first version
        # wrote "" and made the caller's corrected retry raise), and a caller
        # verified once on a call cannot re-verify as someone else.
        if not context.memory.get(CUSTOMER_KEY):
            context.memory.set(CUSTOMER_KEY, result["customer_id"])
            context.memory.set(FIRST_NAME_KEY, result["first_name"])
        elif context.memory.get(CUSTOMER_KEY) != result["customer_id"]:
            return ToolResult(llm_response={
                "status": "not_verified",
                "reason": "already_verified_as_another_customer",
                "next_step": "This call is verified for a different customer. Do not act for this one.",
            })
    public = {k: v for k, v in result.items() if k != "customer_id"}
    return ToolResult(llm_response=public)


@tool(
    description=(
        "Resolve the card the caller named to exactly one of their cards, from its "
        "last four digits and, if they said it, the kind (debit, credit or prepaid). "
        "Returns a card_ref to block, or blocked when the card is not theirs or "
        "more than one card matches."
    )
)
async def select_card(
    card_last_four: str, card_kind: Optional[str] = None, context: ToolContext = None
) -> ToolResult:
    """Select one card.

    Args:
        card_last_four: The last four digits the caller said, as digits, for example 4417.
        card_kind: debit, credit or prepaid, only if the caller said which.
    """
    result = ng.select_card(_service(), _get(context, CUSTOMER_KEY), card_last_four, card_kind)
    if context is not None:
        # A new selection always replaces the old one, so a correction can
        # never leave the previous card confirmed.
        context.memory.set("selected_card_ref", result.get("card_ref", ""))
        context.memory.set("selected_card_label", result.get("card_label", ""))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Block the one card returned by select_card, identified by its card_ref. "
        "Blocks only that card, never a replacement order. The engine asks the "
        "caller to confirm first."
    )
)
async def block_card(card_ref: str, context: ToolContext = None) -> ToolResult:
    """Block one card.

    Args:
        card_ref: The card_ref from select_card, for example NB-CARD-0101.
    """
    result = ng.block_card(
        _service(),
        _get(context, CUSTOMER_KEY),
        _get(context, "selected_card_ref"),
        card_ref,
        request_id=_conversation_id(),
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Read one card's current state from the card service. Use after a block "
        "came back pending, for the same card_ref."
    )
)
async def check_card_status(card_ref: str, context: ToolContext = None) -> ToolResult:
    """Read a card's state.

    Args:
        card_ref: The card_ref of the card to read.
    """
    return ToolResult(llm_response=ng.check_card_status(_service(), _get(context, CUSTOMER_KEY), card_ref))


@tool(
    description=(
        "Route the caller to the card services urgent desk when a block cannot be "
        "confirmed. Returns a reference."
    )
)
async def route_urgent_support(card_ref: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the urgent desk.

    Args:
        card_ref: The card the problem is about.
        reason: One short sentence, for example block not confirmed by the card service.
    """
    return ToolResult(
        llm_response=ng.route_urgent_support(_service(), _get(context, CUSTOMER_KEY), card_ref, reason)
    )


@tool(
    description=(
        "Order a replacement for a card whose block the card service confirmed. "
        "Only when the caller explicitly asks for a replacement."
    )
)
async def order_replacement_card(card_ref: str, context: ToolContext = None) -> ToolResult:
    """Order a replacement card.

    Args:
        card_ref: The blocked card to replace.
    """
    return ToolResult(
        llm_response=ng.order_replacement_card(_service(), _get(context, CUSTOMER_KEY), card_ref)
    )
