"""Dispute-intake tools. The guard runs in lib.disputes, not in the prompt.

The verified customer id and the selected transaction live in memory that only
these tools write (never ``llm_settable``). The model passes a name, a date of
birth, a description of the charge, a transaction reference copied from
``select_transaction`` and the caller's statement.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import disputes as nd

CUSTOMER_KEY = "project.verified_customer_id"
FIRST_NAME_KEY = "project.caller_first_name"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> nd.LedgerService:
    return nd.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


@tool(
    description=(
        "Verify the caller from their full name and date of birth before any "
        "transaction is looked up or disputed. Pass the date as YYYY-MM-DD."
    )
)
async def verify_caller(full_name: str, date_of_birth: str, context: ToolContext = None) -> ToolResult:
    """Verify the caller.

    Args:
        full_name: The caller's first and last name as they said it.
        date_of_birth: Date of birth as YYYY-MM-DD, for example 1990-07-21.
    """
    result = nd.verify_caller(_service(), full_name, date_of_birth)
    if context is not None and result["status"] == "verified":
        # Mantle project memory is write-once, so a failed attempt writes
        # nothing and a call verified as one customer cannot become another.
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
        "Find the one card transaction the caller does not recognise on their own "
        "cards, from what they said: merchant, amount in rupees, date and card "
        "ending. Returns a transaction_ref, or blocked with candidates when the "
        "description matches none or several."
    )
)
async def select_transaction(
    merchant: Optional[str] = None,
    amount_rupees: Optional[str] = None,
    transaction_date: Optional[str] = None,
    card_last_four: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Select one transaction.

    Args:
        merchant: Merchant name as the caller said it, for example Brightmart Online.
        amount_rupees: Amount in rupees as digits, for example 2499.
        transaction_date: Date of the charge as YYYY-MM-DD, only if the caller said it. The year is 2026.
        card_last_four: Last four digits of the card, only if the caller said them.
    """
    result = nd.select_transaction(
        _service(), _get(context, CUSTOMER_KEY), merchant, amount_rupees, transaction_date, card_last_four
    )
    if context is not None:
        # A new selection always replaces the old one, so a correction can
        # never leave the previous charge confirmed.
        context.memory.set("selected_transaction_ref", result.get("transaction_ref", ""))
        context.memory.set("selected_transaction_label", result.get("transaction_label", ""))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "File a dispute for the one transaction returned by select_transaction, with "
        "the caller's statement. The engine reads the charge back and asks the caller "
        "to confirm first. Returns a dispute reference and the next review step; it "
        "never decides a refund."
    )
)
async def file_dispute(transaction_ref: str, customer_statement: str, context: ToolContext = None) -> ToolResult:
    """File one dispute.

    Args:
        transaction_ref: The transaction_ref from select_transaction, for example NB-TXN-3101.
        customer_statement: What the caller said about the charge, in their words, one sentence.
    """
    result = nd.file_dispute(
        _service(),
        _get(context, CUSTOMER_KEY),
        _get(context, "selected_transaction_ref"),
        transaction_ref,
        customer_statement,
        conversation_id=_conversation_id(),
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Look up a dispute filing by its original submission_key after file_dispute "
        "came back pending. Never files anything."
    )
)
async def check_dispute_status(submission_key: str, context: ToolContext = None) -> ToolResult:
    """Look up a filing.

    Args:
        submission_key: The submission_key from file_dispute, for example NB-SUB-1A2B3C4D.
    """
    return ToolResult(llm_response=nd.check_dispute_status(_service(), _get(context, CUSTOMER_KEY), submission_key))


@tool(
    description=(
        "Route a pending dispute to the disputes case owner when its state cannot be "
        "confirmed. Returns a desk reference."
    )
)
async def route_disputes_desk(submission_key: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the disputes desk.

    Args:
        submission_key: The submission_key of the pending filing.
        reason: One short sentence, for example case service could not confirm the dispute.
    """
    return ToolResult(
        llm_response=nd.route_disputes_desk(_service(), _get(context, CUSTOMER_KEY), submission_key, reason)
    )


@tool(
    description=(
        "Block one of the caller's cards when they ask for it. A separate request with "
        "its own reference; it does not change or decide any dispute."
    )
)
async def request_card_block(card_last_four: str, context: ToolContext = None) -> ToolResult:
    """Block a card.

    Args:
        card_last_four: Last four digits of the caller's card, for example 7319.
    """
    return ToolResult(
        llm_response=nd.request_card_block(
            _service(), _get(context, CUSTOMER_KEY), card_last_four, conversation_id=_conversation_id()
        )
    )
