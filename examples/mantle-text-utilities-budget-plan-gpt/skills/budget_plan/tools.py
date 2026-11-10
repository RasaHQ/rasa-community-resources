"""Budget-plan tools. The guard runs in lib.budget, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The selected option (account, option tag, schedule, estimate basis, balance)
is skill memory that only these tools write (never ``llm_settable``), so what
the engine reads back before a request is always the billing service's. Each
value is one short field: Mantle cuts a memory value at 100 characters in the
prompt without saying so.

No tool takes an amount, a number of payments, a date, a balance or a fact.
The model passes the customer's words for an account, an option id copied
from a tool result, a reference, and the customer's own words for a referral.

When ``lib.budget.TOOL_SENDS_RECEIPT`` is on, the request, reconcile, hardship
and support tools send the customer their outcome themselves through
``ToolContext.send`` (never on a replay), so a silent ``complete_skill``
cannot hide the reference.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import budget as ag
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ag.BillingService:
    return ag.service_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> str:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or ag.SESSION_CUSTOMER_ID


def _memory(context: Optional[ToolContext]) -> dict:
    return {key: (context.memory.get(key) if context is not None else None) or None for key in ag.MEMORY_KEYS}


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
        "Read the budget-plan quote for one of the signed-in customer's accounts from Amber Grid's billing "
        "service: the usage estimate a budget amount is based on, the outstanding balance, and each authorized "
        "option's schedule with its option id. Use it to explain a budget amount or a balance. Changes nothing."
    )
)
async def get_budget_quote(account: str, context: ToolContext = None) -> ToolResult:
    """Read the quote.

    Args:
        account: The account as the customer named it, for example home electricity or AG-6120.
    """
    return ToolResult(llm_response=ag.get_budget_quote(_service(), _customer(context), account))


@tool(
    description=(
        "Select one budget option the customer chose, by the option_id a tool returned, so the engine can read "
        "its schedule, estimate and the balance back before a request. Refuses options the billing service did "
        "not authorize."
    )
)
async def select_budget_option(option_id: str, context: ToolContext = None) -> ToolResult:
    """Select an option.

    Args:
        option_id: The option_id from get_budget_quote, for example BP-6120-A.
    """
    result, memory = ag.select_budget_option(_service(), _customer(context), option_id)
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Request the selected budget option for the customer. The engine reads the schedule, the estimate and "
        "the outstanding balance back and asks the customer first. Returns a request reference, pending when the "
        "billing system has not confirmed it, or blocked."
    )
)
async def request_budget_option(option_id: str, context: ToolContext = None) -> ToolResult:
    """Request the selected option.

    Args:
        option_id: The option_id of the selected option, for example BP-6120-A.
    """
    conversation = conversation_from_events(context.events) if context is not None else ag.Conversation()
    result, memory = ag.request_budget_option(_service(), _customer(context), _memory(context), conversation,
                                              option_id, _conversation_id())
    _write_memory(context, memory)
    await _send_receipt(context, "request_budget_option", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Look up a budget plan request by its request id (AG-BPQ-...) or reference (AG-BPR-...). After a request "
        "the billing system did not confirm, this asks about the same request. Never requests anything."
    )
)
async def check_budget_request(reference: str, context: ToolContext = None) -> ToolResult:
    """Look up a request.

    Args:
        reference: A request id such as AG-BPQ-1A2B3C or a reference such as AG-BPR-4D5E6F.
    """
    result = ag.check_budget_request(_service(), _customer(context), reference)
    await _send_receipt(context, "check_budget_request", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Refer the customer to Amber Grid's hardship team when they say they cannot afford the authorized "
        "options or ask for help paying. Keeps the option they were considering, or their recorded request, with "
        "the referral. Stops the option flow. Decides nothing and offers no terms."
    )
)
async def route_hardship_referral(account: str, customer_words: str, context: ToolContext = None) -> ToolResult:
    """Open a hardship referral.

    Args:
        account: The account as the customer named it, for example home gas or AG-6121.
        customer_words: What the customer said about their situation, in their words.
    """
    result, memory = ag.route_hardship_referral(_service(), _customer(context), account, customer_words,
                                                _memory(context), _conversation_id())
    _write_memory(context, memory)
    await _send_receipt(context, "route_hardship_referral", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass the customer to Amber Grid's billing support team, for example to review an option with a person "
        "before choosing, or to change a request that is already recorded. Returns a support reference. Changes "
        "nothing on the account."
    )
)
async def route_billing_support(account: str, note: str, context: ToolContext = None) -> ToolResult:
    """Route to billing support.

    Args:
        account: The account as the customer named it, for example AG-6120.
        note: One short sentence saying what the customer wants.
    """
    result, memory = ag.route_billing_support(_service(), _customer(context), account, note, _memory(context),
                                              _conversation_id())
    _write_memory(context, memory)
    await _send_receipt(context, "route_billing_support", result)
    return ToolResult(llm_response=result)
