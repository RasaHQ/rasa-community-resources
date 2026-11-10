"""Subscription-change tools. The guard runs in lib.subscriptions, not in the prompt.

The signed-in member is project memory that only the session tool writes. The
selected change (subscription, change tag, label, effective time and
entitlement line) is skill memory that only ``select_subscription_change``
writes (never ``llm_settable``), so what the engine reads back for
confirmation is always the subscription service's. Each value is one short
field: Mantle cuts a memory value at 100 characters in the prompt without
saying so.

No tool takes a date, an amount, a revision, a member id or a fact. The model
passes the member's words for a subscription, one of three change types, and
a note for a hand-off.

When ``lib.subscriptions.TOOL_SENDS_RECEIPT`` is on,
``apply_subscription_change``, ``check_change_status`` and
``route_subscription_support`` send the member their outcome themselves
through ``ToolContext.send``, so a silent ``complete_skill`` cannot hide the
reference. A replayed result sends nothing.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import subscriptions as ws
from lib.conversation import conversation_from_events

MEMBER_KEY = "project.member_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ws.SubscriptionService:
    return ws.service_for(_conversation_id())


def _member(context: Optional[ToolContext]) -> str:
    return (context.memory.get(MEMBER_KEY) if context is not None else None) or ws.SESSION_MEMBER_ID


def _write_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = ws.customer_receipt(tool_name, result) if ws.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "List the signed-in member's Willow Shop subscriptions: price, paid-through date, next charge, benefits "
        "and state, plus their loyalty points. Changes nothing."
    )
)
async def list_subscriptions(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=ws.list_subscriptions(_service(), _member(context)))


@tool(
    description=(
        "Show what each of the three changes would do to one subscription: stop the renewal, pause it, or cancel "
        "now. For each, the effective time, what the member keeps and loses, any refund and forfeited points. "
        "Changes nothing."
    )
)
async def compare_subscription_changes(subscription: str, context: ToolContext = None) -> ToolResult:
    """Compare the changes.

    Args:
        subscription: The subscription as the member named it, for example Willow Plus, coffee or WS-SUB-3302.
    """
    return ToolResult(llm_response=ws.compare_subscription_changes(_service(), _member(context), subscription))


@tool(
    description=(
        "Select the one change the member asked for, so the engine can read its effective time and entitlements "
        "back for confirmation. change_type is stop_renewal, pause or cancel_now."
    )
)
async def select_subscription_change(subscription: str, change_type: str, context: ToolContext = None) -> ToolResult:
    """Select a change.

    Args:
        subscription: The subscription as the member named it, for example Willow Plus or WS-SUB-3301.
        change_type: stop_renewal (no further charges, access to the end of the paid period), pause, or cancel_now (access ends today).
    """
    result, memory = ws.select_subscription_change(_service(), _member(context), subscription, change_type)
    _write_memory(context, memory)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Make the selected change on the subscription service. The engine reads the change back and asks the "
        "member first. Returns a change reference with the effective time and remaining entitlements, pending "
        "when the service has not confirmed it, or blocked."
    )
)
async def apply_subscription_change(subscription: str, change_type: str, context: ToolContext = None) -> ToolResult:
    """Make the selected change.

    Args:
        subscription: The subscription id of the selected change, for example WS-SUB-3301.
        change_type: The selected change type: stop_renewal, pause or cancel_now.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in ws.MEMORY_KEYS}
    conversation = conversation_from_events(context.events) if context is not None else ws.Conversation()
    result = ws.apply_subscription_change(_service(), _member(context), memory, conversation, subscription,
                                          change_type, _conversation_id())
    await _send_receipt(context, "apply_subscription_change", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "When a change came back pending, read it back from the subscription service by its original request "
        "key and revision. Sends no new command. Returns the confirmed change reference, or still pending."
    )
)
async def check_change_status(subscription: str, context: ToolContext = None) -> ToolResult:
    """Check a pending change.

    Args:
        subscription: The subscription id of the pending change, for example WS-SUB-3303.
    """
    result = ws.check_change_status(_service(), _member(context), subscription, _conversation_id())
    await _send_receipt(context, "check_change_status", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass a request this chat cannot handle to Willow Shop's subscription support team, for example a second "
        "change to a subscription already changed here, or terms none of the three options has. Returns a "
        "support reference. Changes nothing on the subscription."
    )
)
async def route_subscription_support(subscription: str, note: str, context: ToolContext = None) -> ToolResult:
    """Route to subscription support.

    Args:
        subscription: The subscription as the member named it, for example WS-SUB-3301.
        note: One short sentence saying what the member wants.
    """
    result = ws.route_subscription_support(_service(), _member(context), subscription, note, _conversation_id())
    await _send_receipt(context, "route_subscription_support", result)
    return ToolResult(llm_response=result)
