"""Repayment-plan tools. The guard runs in lib.repayment, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The staged plan is skill memory that only these tools write (never
``llm_settable``), so the plan the engine reads back for confirmation is
always the offer ``select_plan_offer`` staged. Hardship and withdrawals are
read from the customer's own messages in the tracker (on a voice call, what
speech-to-text heard), never from the model's arguments.

Every outcome with a reference is sent to the customer by the tool itself,
through ``ToolContext.send``, before the model writes anything.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import repayment as rp
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _state() -> rp.CallState:
    return rp.state_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _customer(context: Optional[ToolContext]) -> Optional[str]:
    return _get(context, CUSTOMER_KEY)


def _conversation(context: Optional[ToolContext]) -> rp.Conversation:
    return conversation_from_events(context.events) if context is not None else rp.Conversation()


def _set_plan(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key in rp.PLAN_MEMORY_KEYS:
        context.memory.set(key, values.get(key, ""))


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = rp.customer_receipt(tool_name, result) if rp.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)
        result["receipt_sent_to_customer"] = True


@tool(
    description=(
        "The payment plans this past-due account can have now, with exact amounts and dates, and the "
        "hardship team beside them. Returns no plans when the customer has said they cannot meet basic "
        "expenses, or when plans are switched off for the account."
    )
)
async def get_plan_offers(account_ending: str, context: ToolContext = None) -> ToolResult:
    """Current plans for one account.

    Args:
        account_ending: The account's last four digits, for example 4471.
    """
    result = rp.get_plan_offers(_customer(context), account_ending, _conversation(context), _state())
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Stage the plan the customer picked so the engine can read its exact terms back. Pass the offer_id "
        "from get_plan_offers, or for a plan the customer describes (from a letter, or their own amount), "
        "its number of payments and amount. Records nothing."
    )
)
async def select_plan_offer(
    account_ending: str,
    offer_id: Optional[str] = None,
    installments: Optional[int] = None,
    amount_usd: Optional[float] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Stage one plan.

    Args:
        account_ending: The account's last four digits, for example 4471.
        offer_id: The offer_id from get_plan_offers, for example OFR-4471-3M.
        installments: Number of monthly payments the customer described, if there is no offer_id.
        amount_usd: Amount of each payment the customer described, in dollars, if there is no offer_id.
    """
    state = _state()
    result, memory = rp.select_plan_offer(_customer(context), account_ending, _conversation(context), state,
                                          offer_id, installments, amount_usd)
    _set_plan(context, memory or {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the staged plan as the customer's chosen repayment plan. The engine reads the exact terms "
        "back and asks the customer to confirm first. Records only a current offer the customer confirmed; "
        "recording a plan is not a payment."
    )
)
async def record_plan_choice(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Record one confirmed plan.

    Args:
        offer_id: The offer_id of the staged plan, for example OFR-4471-3M.
    """
    state = _state()
    memory = {key: _get(context, key) for key in rp.PLAN_MEMORY_KEYS}
    result = rp.record_plan_choice(_customer(context), _conversation(context), state, offer_id, memory,
                                   _conversation_id())
    if result["status"] == "succeeded" or state.staged is None:
        _set_plan(context, {})
    await _send_receipt(context, "record_plan_choice", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "The customer takes back a plan choice: clears a staged plan, or withdraws a plan recorded on this "
        "call. Nothing is recorded and no debit is scheduled."
    )
)
async def withdraw_plan_choice(account_ending: Optional[str] = None, context: ToolContext = None) -> ToolResult:
    """Withdraw a plan choice.

    Args:
        account_ending: The account's last four digits, if known.
    """
    result = rp.withdraw_plan_choice(_state(), account_ending)
    _set_plan(context, {})
    await _send_receipt(context, "withdraw_plan_choice", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Refer the customer to the hardship team for their account when they cannot meet basic expenses or "
        "ask for hardship help. Stops plan offers for the rest of the call. If the team cannot take "
        "referrals, the request is kept and a person calls back."
    )
)
async def request_hardship_referral(account_ending: str, summary: Optional[str] = None,
                                    context: ToolContext = None) -> ToolResult:
    """Hardship referral.

    Args:
        account_ending: The account's last four digits, for example 4471.
        summary: One short sentence, in the customer's words, of why they need help.
    """
    result = rp.request_hardship_referral(_customer(context), account_ending, summary, _state(),
                                          _conversation_id())
    _set_plan(context, {})
    await _send_receipt(context, "request_hardship_referral", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Ask a person from Northgate to call the customer back about an account, when plans are switched "
        "off for it or the customer prefers to talk to someone. Records no plan."
    )
)
async def request_human_callback(account_ending: str, topic: Optional[str] = None,
                                 context: ToolContext = None) -> ToolResult:
    """Human callback.

    Args:
        account_ending: The account's last four digits, for example 0938.
        topic: What the call is about, in a few words.
    """
    result = rp.request_human_callback(_customer(context), account_ending, topic, _state(), _conversation_id())
    await _send_receipt(context, "request_human_callback", result)
    return ToolResult(llm_response=result)
