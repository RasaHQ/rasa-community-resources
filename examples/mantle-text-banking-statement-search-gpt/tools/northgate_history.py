"""Shared Northgate Bank tools: session binding and certified statements.

The customer id always comes from project memory, which load_caller_profile
writes at session start (the web-chat session is already signed in). The
model supplies an account name and a month; it never supplies a customer id,
a balance or a fact.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import history as nb

CUSTOMER_KEY = "project.customer_id"


def session_customer_id(context: Optional[ToolContext]) -> str:
    if context is None:
        return nb.SESSION_CUSTOMER_ID
    return context.memory.get(CUSTOMER_KEY) or nb.SESSION_CUSTOMER_ID


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = nb.session_profile()
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once on the pinned engine: the session is bound
        # once, here. Each value is one short field (see nb.MEMORY_VALUE_LIMIT).
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.account_names", profile["account_names"])
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"],
                                    "accounts": profile["account_names"]})


@tool(
    description=(
        "Read a certified statement for one of the caller's accounts: the billing cycle, the closing balance and "
        "the issue date. Pass the month the cycle ends in, or latest. Statement cycles are not calendar months."
    )
)
async def get_statement(account: str, month: Optional[str] = None, context: ToolContext = None) -> ToolResult:
    """Read a statement.

    Args:
        account: The account as the caller named it, for example everyday checking.
        month: The month the statement's cycle ends in, for example March 2026, or latest.
    """
    return ToolResult(llm_response=nb.get_statement(session_customer_id(context), account, month))
