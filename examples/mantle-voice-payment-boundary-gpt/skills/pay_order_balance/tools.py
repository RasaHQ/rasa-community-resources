"""Order-payment tools. The guard runs in lib.payments, not in the prompt.

No tool takes card details: there is no card, expiry or security-code
parameter anywhere, and an argument that carries card digits is refused and
never echoed. Payment happens only on the processor's hosted page, sent as a
link by text or email to the contact details on the account.

The signed-in customer is project memory that only the session tool writes.
The prepared order and channel are skill memory that only
``prepare_secure_payment`` writes (never ``llm_settable``), so what the engine
reads back for confirmation is what the tools checked. The caller's messages
come from the tracker (on a voice call, what speech-to-text heard, with card
details already removed by ``engines/deepgram_pci.py``).

When ``lib.payments.TOOL_SENDS_RECEIPT`` is on, the tools send the caller
their outcome themselves through ``ToolContext.send``: link sent, paid with
the processor reference, not confirmed, or left unpaid. On voice the tool
waits while that receipt is spoken, which is why ``agent.yml`` sets
``tool_timeout: 30``.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import UserUttered

from lib import payments as wp

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> wp.PaymentService:
    return wp.service_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or None


def _user_texts(context: Optional[ToolContext]) -> list[str]:
    """The caller's own messages. /session_start and other engine intents are not words."""
    if context is None:
        return []
    return [e.text or "" for e in context.events
            if isinstance(e, UserUttered) and not (e.text or "").startswith("/")]


def _user_turn(context: Optional[ToolContext]) -> int:
    return len(_user_texts(context))


def _memory(context: Optional[ToolContext]) -> dict:
    return {key: (context.memory.get(key) if context is not None else None) or None for key in wp.MEMORY_KEYS}


def _set_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key in wp.MEMORY_KEYS:
        context.memory.set(key, values.get(key, ""))


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = wp.customer_receipt(tool_name, result) if wp.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)
        result["receipt_sent_to_caller"] = True


@tool(
    description=(
        "Look up the balance due on one of the signed-in customer's orders and why it is on hold. "
        "Takes the order number only. Never takes card details."
    )
)
async def look_up_order_balance(order_number: str, context: ToolContext = None) -> ToolResult:
    """Look up an order's balance.

    Args:
        order_number: The Willow Shop order number the caller gave, for example WS-10517.
    """
    return ToolResult(llm_response=wp.look_up_order_balance(_service(), _customer(context), order_number))


@tool(
    description=(
        "Check that a payment can go through an approved secure channel and set up the confirmation: "
        "a processor-hosted payment link by text or by email to the contact details on the account. "
        "Sends nothing. Refuses any other channel, and refuses when card details are in the call record."
    )
)
async def prepare_secure_payment(order_number: str, channel: str, context: ToolContext = None) -> ToolResult:
    """Prepare a secure payment link.

    Args:
        order_number: The order to pay, for example WS-10517.
        channel: text or email, as the caller chose.
    """
    result, memory = wp.prepare_secure_payment(_service(), _customer(context), _user_texts(context),
                                               wp.redaction_active(), order_number, channel)
    if memory:
        _set_memory(context, memory)
    elif result["status"] in ("blocked", "cancelled", "nothing_owed"):
        _set_memory(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the prepared secure payment link. The engine reads the order, amount and channel back and "
        "asks the caller to confirm first. The payment stays pending until the processor confirms it."
    )
)
async def send_secure_payment_link(order_number: str, context: ToolContext = None) -> ToolResult:
    """Send the prepared link.

    Args:
        order_number: The order prepared with prepare_secure_payment, for example WS-10517.
    """
    result = wp.send_secure_payment_link(_service(), _customer(context), _user_texts(context),
                                         wp.redaction_active(), _memory(context), order_number,
                                         _user_turn(context))
    if result["status"] == "link_sent":
        _set_memory(context, {})
    await _send_receipt(context, "send_secure_payment_link", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Read the payment processor's status for an order's secure payment: paid with a verified processor "
        "reference, still pending, expired or not confirmed. The caller's word is never a receipt."
    )
)
async def check_payment_status(order_number: str, context: ToolContext = None) -> ToolResult:
    """Check the processor.

    Args:
        order_number: The order, for example WS-10517.
    """
    result = wp.check_payment_status(_service(), _customer(context), order_number, _user_turn(context))
    await _send_receipt(context, "check_payment_status", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Leave an order's payment pending when the caller does not want the secure payment step, and give "
        "them the approved alternative. Charges nothing."
    )
)
async def leave_payment_pending(order_number: str, context: ToolContext = None) -> ToolResult:
    """Leave the payment pending.

    Args:
        order_number: The order, for example WS-10517.
    """
    result = wp.leave_payment_pending(_service(), _customer(context), order_number)
    if result["status"] == "pending":
        _set_memory(context, {})
    await _send_receipt(context, "leave_payment_pending", result)
    return ToolResult(llm_response=result)
