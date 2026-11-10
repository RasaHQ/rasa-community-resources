"""Payoff-quote tools. The guard runs in lib.servicing, not in the prompt.

The presented quote lives in skill memory that only present_payoff_quote
writes (never ``llm_settable``), one short field per value, so the quote the
engine asks the caller about before sending instructions is always the one
the servicing system presented. The model passes the caller's words for a
loan and a ``quote_ref`` copied from a tool result. No tool takes an amount,
a date or a fact.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import servicing as nb

QUOTE_FIELDS = ("quote_ref", "quote_loan", "quote_amount", "quote_good_through")


# Same helpers as tools/northgate_loans.py. Mantle loads each tool module on
# its own, so skill tools import only from lib/, never from tools/.
def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> nb.Servicing:
    return nb.servicing_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> str:
    if context is None:
        return nb.DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or nb.DEMO_CUSTOMER_ID


def quote_memory(result: dict) -> dict[str, str]:
    """Skill memory for a presented quote; empty strings clear it for anything else."""
    if result.get("status") != "presented":
        return {key: "" for key in QUOTE_FIELDS}
    return {
        "quote_ref": result["quote_ref"],
        "quote_loan": result["loan"],
        "quote_amount": result["payoff_amount"],
        "quote_good_through": result["good_through"],
    }


def _set(context: Optional[ToolContext], values: dict[str, str]) -> None:
    if context is not None:
        for key, value in values.items():
            context.memory.set(key, value)


@tool(
    description=(
        "Present the current payoff quote for one of the customer's loans from the servicing system. "
        "Returns the dated quote (amount, included charges, good-through time, next step), or blocked "
        "with a reason and no amount."
    )
)
async def present_payoff_quote(loan: str, context: ToolContext = None) -> ToolResult:
    """Present a payoff quote.

    Args:
        loan: The loan as the customer named it, for example my car loan, the personal loan, or ending 4417.
    """
    result = nb.present_payoff_quote(service(), session_customer_id(context), loan)
    _set(context, quote_memory(result))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Ask the servicing system to issue a new payoff quote for a loan whose quote expired or lacks "
        "its charge breakdown. Returns issued with a quote_ref (then call present_payoff_quote), or "
        "unavailable. States no amount."
    )
)
async def refresh_payoff_quote(loan: str, context: ToolContext = None) -> ToolResult:
    """Refresh a payoff quote.

    Args:
        loan: The loan as the customer named it.
    """
    return ToolResult(llm_response=nb.refresh_payoff_quote(service(), session_customer_id(context), loan))


@tool(
    description=(
        "Send payoff instructions for the quote present_payoff_quote presented, to the customer's secure "
        "message inbox. The engine asks the customer to confirm first. Takes no payment."
    )
)
async def send_payoff_instructions(quote_ref: str, context: ToolContext = None) -> ToolResult:
    """Send payoff instructions.

    Args:
        quote_ref: The quote_ref from present_payoff_quote, for example PQ-2290-0930.
    """
    presented = context.memory.get("quote_ref") if context is not None else None
    result = nb.send_payoff_instructions(service(), session_customer_id(context), presented, quote_ref)
    return ToolResult(llm_response=result)
