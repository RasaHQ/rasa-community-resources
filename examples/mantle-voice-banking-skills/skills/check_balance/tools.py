"""Tools local to the check_balance skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, username_from_context


@tool(description="Look up account balance by account number for the current customer.")
async def check_balance(account_number: str, context: ToolContext = None) -> ToolResult:
    """Look up account balance by account number.

    Args:
        account_number: The customer's account number (digits).
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    row = db.run_query(
        "SELECT balance, type FROM accounts WHERE user_id = ? AND number = ?",
        (user_id, account_number),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "account_not_found",
                "account_number": account_number,
                "hint": "Ask the customer for a valid account number from their accounts.",
            }
        )

    balance, acc_type = row
    if context is not None:
        context.memory.set("account_number", account_number)
        context.memory.set("account_balance", float(balance))

    return ToolResult(
        llm_response={
            "ok": True,
            "account_number": account_number,
            "account_type": acc_type,
            "balance": float(balance),
            "currency": "USD",
        }
    )
