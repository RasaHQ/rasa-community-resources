"""Shared Northgate tools, used by more than one skill.

The customer id always comes from project memory, which load_caller_profile
writes at session start. Payment state lives in one in-process service per
conversation (lib.northgate.service_for), keyed by the conversation id.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import northgate as ng


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> ng.PaymentsService:
    return ng.service_for(conversation_id())


def session_customer_id(context: ToolContext | None) -> str:
    """The customer bound to this session, from trusted project memory."""
    if context is None:
        return ng.DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or ng.DEMO_CUSTOMER_ID


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = ng.caller_profile(service())
    if context is not None and not context.memory.get("project.customer_id"):
        # Project memory is write-once, so the session stays bound to one customer.
        context.memory.set("project.customer_id", profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.accounts", "; ".join(profile["accounts"]))
        context.memory.set("project.payees", "; ".join(profile["payees"]))
    return ToolResult(llm_response={"ok": True, **profile})


@tool(
    description=(
        "Read the balance of one of the customer's accounts. Information only: "
        "it needs just the signed-in session and authorises no payment."
    )
)
async def get_balance(account: str, context: ToolContext = None) -> ToolResult:
    """Read an account balance.

    Args:
        account: The account, for example "current", "savings" or NB-ACC-3101.
    """
    return ToolResult(llm_response=ng.get_balance(service(), session_customer_id(context), account))
