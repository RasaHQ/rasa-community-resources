"""Shared Northgate Bank loan-servicing tools, used by more than one skill.

The customer id always comes from project memory, which load_caller_profile
writes at session start (the web-chat session is already signed in). The
model supplies the caller's words for a loan and short notes; it never
supplies a customer id, an amount, a date, a fact or an outcome.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import servicing as nb

CUSTOMER_KEY = "project.customer_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> nb.Servicing:
    return nb.servicing_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> str:
    """The customer bound to this signed-in session, from trusted project memory."""
    if context is None:
        return nb.DEMO_CUSTOMER_ID
    return context.memory.get(CUSTOMER_KEY) or nb.DEMO_CUSTOMER_ID


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = nb.caller_profile(svc=service())
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once; the session is bound once, here. One
        # short field per loan, because Mantle cuts a longer value at 100
        # characters in the prompt without saying so.
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        for key, label in profile["loans"].items():
            context.memory.set(f"project.{key}", label)
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"],
                                    "loans": list(profile["loans"].values())})


@tool(
    description=(
        "Read one of the customer's loans: principal balance at the last statement and the next "
        "payment. A view only. It is not a payoff amount and never closes a loan."
    )
)
async def get_loan_balance(loan: str, context: ToolContext = None) -> ToolResult:
    """Read a loan balance.

    Args:
        loan: The loan as the customer named it, for example my car loan, the personal loan, or ending 2290.
    """
    return ToolResult(llm_response=nb.get_loan_balance(service(), session_customer_id(context), loan))


@tool(
    description=(
        "Book a callback from the loan servicing team when a payoff quote cannot be given here "
        "(the quote source is unavailable or the loan has no servicing route). Returns a callback reference."
    )
)
async def schedule_servicing_callback(loan: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Schedule a servicing callback.

    Args:
        loan: The loan as the customer named it.
        reason: One short sentence, for example payoff quote source unavailable.
    """
    return ToolResult(
        llm_response=nb.schedule_servicing_callback(service(), session_customer_id(context), loan, reason)
    )


@tool(
    description=(
        "Refer the customer to the loan servicing hardship team when they say they are struggling to pay. "
        "Stops the payoff flow. Returns a referral reference. Gives no advice."
    )
)
async def route_hardship_support(loan: str, note: str, context: ToolContext = None) -> ToolResult:
    """Route to hardship support.

    Args:
        loan: The loan the customer is struggling with, as they named it, or empty if they did not say.
        note: One short sentence in the customer's terms, for example lost job, behind on payments.
    """
    return ToolResult(
        llm_response=nb.route_hardship_support(service(), session_customer_id(context), loan, note)
    )
