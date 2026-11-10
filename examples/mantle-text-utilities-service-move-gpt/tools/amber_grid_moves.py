"""Amber Grid tools shared by the move skills: session binding, service status, order check, review.

The chat runs for a signed-in customer, so the session, not the customer's
words, says whose services these are. The customer id always comes from
project memory, which only ``load_customer_profile`` writes. The guard runs in
lib.moves, not in the prompt. No tool here closes a service.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import moves as ag

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ag.MoveService:
    return ag.service_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> str:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or ag.SESSION_CUSTOMER_ID


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = ag.customer_receipt(tool_name, result) if ag.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the signed-in customer's profile and service list into project memory at session start.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    profile = ag.caller_profile(_service())
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
        "Read the current service at one of the signed-in customer's addresses now: whether it is on, the day it "
        "stays on through if a move is scheduled, and any move order or review. Changes nothing."
    )
)
async def get_service_status(address: str, context: ToolContext = None) -> ToolResult:
    """Read one current service.

    Args:
        address: The customer's address or service as they named it, for example 12 Wren Street or AG-SP-1204.
    """
    return ToolResult(llm_response=ag.service_status(_service(), _customer(context), address))


@tool(
    description=(
        "Look up a move by draft_id (AG-MVD-...) or move-order reference (AG-MOV-...). After a submission that was "
        "not acknowledged, this asks the move-order system about the same draft. Never submits anything."
    )
)
async def check_move_order(reference: str, context: ToolContext = None) -> ToolResult:
    """Look up a move.

    Args:
        reference: A draft_id such as AG-MVD-3A9C1 or a move-order reference such as AG-MOV-40718C.
    """
    result = ag.check_move_order(_service(), _customer(context), reference)
    await _send_receipt(context, "check_move_order", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Route a move draft to Amber Grid's service lifecycle team for review when the new address cannot be "
        "resolved or the move-order system cannot confirm the order. Holds any closure: the current service stays "
        "on as it is. Returns a review reference; it schedules nothing."
    )
)
async def route_move_review(draft_id: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route a move draft for review.

    Args:
        draft_id: The draft_id from start_move_draft, for example AG-MVD-3A9C1.
        reason: One short sentence, for example new address not in the premises register.
    """
    result = ag.route_move_review(_service(), _customer(context), draft_id, reason, _conversation_id())
    await _send_receipt(context, "route_move_review", result)
    return ToolResult(llm_response=result)
