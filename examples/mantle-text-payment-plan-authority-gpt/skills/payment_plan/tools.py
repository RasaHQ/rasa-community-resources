"""Payment-plan tools. The guard runs in lib.plans, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The selected offer (account, offer tag, terms line) is skill memory that only
these tools write (never ``llm_settable``), so the terms the engine reads back
for acceptance are always the billing service's. Each value is one short
field: Mantle cuts a memory value at 100 characters in the prompt without
saying so.

No tool takes an amount, a number of payments, a date or a fact. The model
passes the customer's words for an account, an offer id copied from a tool
result, and the customer's own words for a referral.

When ``lib.plans.TOOL_SENDS_RECEIPT`` is on, ``accept_plan_offer``,
``route_hardship_referral`` and ``route_billing_support`` send the customer
their outcome themselves through ``ToolContext.send``, so a silent
``complete_skill`` cannot hide the reference.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import plans as ag
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
    return ((context.memory.get(CUSTOMER_KEY) if context is not None else None) or ag.SESSION_CUSTOMER_ID)


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
        "Read the payment-plan offers Amber Grid's billing service has authorized for one of the signed-in "
        "customer's overdue accounts: each offer's id, number of payments, amount, first due date and total, "
        "plus any expired offers and a plan already recorded. Changes nothing."
    )
)
async def get_plan_offers(account: str, context: ToolContext = None) -> ToolResult:
    """Read the offers.

    Args:
        account: The account as the customer named it, for example home electricity or AG-4471.
    """
    return ToolResult(llm_response=ag.get_plan_offers(_service(), _customer(context), account))


@tool(
    description=(
        "Select one offer the customer chose, by the offer_id a tool returned, so the engine can read its terms "
        "back for acceptance. Refuses terms the billing service did not authorize and expired offers."
    )
)
async def select_plan_offer(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Select an offer.

    Args:
        offer_id: The offer_id from get_plan_offers or refresh_plan_offer, for example AG-OFR-4471-A.
    """
    result, memory = ag.select_plan_offer(_service(), _customer(context), offer_id)
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the customer's acceptance of the selected offer. The engine reads the billing service's terms "
        "back and asks the customer first. Returns a plan reference with the recorded terms, or blocked."
    )
)
async def accept_plan_offer(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Accept the selected offer.

    Args:
        offer_id: The offer_id of the selected offer, for example AG-OFR-4471-A.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in ag.MEMORY_KEYS}
    conversation = conversation_from_events(context.events) if context is not None else ag.Conversation()
    result = ag.accept_plan_offer(_service(), _customer(context), memory, conversation, offer_id, _conversation_id())
    await _send_receipt(context, "accept_plan_offer", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Withdraw an account's expired offers and ask the billing service for current ones. Returns the "
        "refreshed offers, or no_eligible_offer when none can be offered."
    )
)
async def refresh_plan_offer(account: str, context: ToolContext = None) -> ToolResult:
    """Refresh the offers.

    Args:
        account: The account as the customer named it, for example home gas or AG-4472.
    """
    result, memory = ag.refresh_plan_offer(_service(), _customer(context), account)
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Refer the customer to Amber Grid's hardship team when they cannot afford the offered plan, ask for "
        "terms no offer has, or no eligible offer remains. Stops the offer flow. Decides nothing."
    )
)
async def route_hardship_referral(account: str, customer_words: str, context: ToolContext = None) -> ToolResult:
    """Open a hardship referral.

    Args:
        account: The account as the customer named it, for example flat electricity or AG-5820.
        customer_words: What the customer said about what they can afford, in their words.
    """
    result, memory = ag.route_hardship_referral(_service(), _customer(context), account, customer_words,
                                                _conversation_id())
    _write_memory(context, memory)
    await _send_receipt(context, "route_hardship_referral", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass a request this chat cannot handle to Amber Grid's billing support team, for example changing a "
        "plan that is already recorded. Returns a support reference. Changes nothing on the account."
    )
)
async def route_billing_support(account: str, note: str, context: ToolContext = None) -> ToolResult:
    """Route to billing support.

    Args:
        account: The account as the customer named it, for example AG-4471.
        note: One short sentence saying what the customer wants.
    """
    result = ag.route_billing_support(_service(), _customer(context), account, note, _conversation_id())
    await _send_receipt(context, "route_billing_support", result)
    return ToolResult(llm_response=result)
