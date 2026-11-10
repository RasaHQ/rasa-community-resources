"""Juniper Mobile tools shared by the skills: session binding, account status, ending contact.

The chat runs for a signed-in customer, so the session, not the customer's
words, says whose services these are. The customer id always comes from
project memory, which only ``load_customer_profile`` writes. The guard runs in
lib.retention, not in the prompt.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import retention as jm
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _desk() -> jm.RetentionDesk:
    return jm.desk_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> str:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or jm.SESSION_CUSTOMER_ID


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = jm.customer_receipt(tool_name, result) if jm.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the signed-in customer's profile and service list into project memory at session start.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    profile = jm.caller_profile(_desk())
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (MEMORY_VALUE_LIMIT).
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.service_list", profile["service_list"])
        context.memory.set("project.today", profile["today"])
    public = {k: v for k, v in profile.items() if k != "customer_id"}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "Read one of the signed-in customer's services: plan, monthly price, contract, any cancellation request or "
        "accepted offer, and whether retention contact is permitted. Changes nothing."
    )
)
async def get_account_status(service: str, context: ToolContext = None) -> ToolResult:
    """Read one service.

    Args:
        service: The service as the customer named it, for example my mobile or the home fibre.
    """
    conversation = conversation_from_events(context.events) if context is not None else jm.Conversation()
    return ToolResult(llm_response=jm.account_status(_desk(), _customer(context), conversation, service))


@tool(
    description=(
        "End retention and win-back contact for every account of the signed-in customer, and send the withdrawal to "
        "the campaign dispatch. Use when the customer says to stop contacting them or to stop sending offers."
    )
)
async def withdraw_contact(context: ToolContext = None) -> ToolResult:
    result = jm.withdraw_contact(_desk(), _customer(context), _conversation_id())
    await _send_receipt(context, "withdraw_contact", result)
    return ToolResult(llm_response=result)
