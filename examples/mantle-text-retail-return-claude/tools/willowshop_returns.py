"""Willow Shop tools shared by the returns skills: session binding, status, desk.

The chat widget runs on the Willow Shop website for a signed-in customer, so
the session, not the customer's words, says whose orders these are. The
customer id always comes from project memory, which only
``load_session_customer`` writes. The guard runs in lib.returns, not in the
prompt; the model never supplies a customer id, a contract fact or an outcome.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import returns as wr

CUSTOMER_KEY = "project.customer_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> wr.ReturnsService:
    return wr.service_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or None


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_session_customer(context: ToolContext = None) -> ToolResult:
    profile = wr.session_profile()
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (Mantle cuts memory values at 100
        # characters in the prompt; see lib.returns.MEMORY_VALUE_LIMIT).
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.order_numbers", ", ".join(profile["order_numbers"]))
    public = {k: v for k, v in profile.items() if k != "customer_id"}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "Look up an existing return or exchange request: by its submission_key or RMA "
        "reference, or by order number and item description. Returns each stage "
        "separately (authorization, shipment, inspection, refund, replacement). Never "
        "creates a request or a label."
    )
)
async def check_return_status(
    reference: str,
    item_description: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Look up a return.

    Args:
        reference: A submission_key (WS-RSUB-...), an RMA reference (WS-RMA-...), or an order number such as WS-20611.
        item_description: With an order number, the item in the customer's words, for example the chinos.
    """
    return ToolResult(
        llm_response=wr.check_return_status(service(), session_customer_id(context), reference, item_description)
    )


@tool(
    description=(
        "Route an exception (an item that is not eligible but the customer asks for an "
        "exception, or a damaged item) or a request whose authorization cannot be "
        "confirmed to the returns service owner. Returns a desk reference; it decides "
        "nothing and makes no label."
    )
)
async def route_returns_desk(reference: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the returns desk.

    Args:
        reference: The item_ref from find_order_item (for example WS-20644-1) or the submission_key of a pending request.
        reason: One short sentence, for example customer asks for an exception to the return window.
    """
    return ToolResult(
        llm_response=wr.route_returns_desk(service(), session_customer_id(context), reference, reason)
    )
