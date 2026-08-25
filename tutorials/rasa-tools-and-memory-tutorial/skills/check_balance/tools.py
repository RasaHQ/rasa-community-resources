"""LOCAL tool for check_balance — reading a balance is this skill's job alone."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.directory import customer_by_id


@tool(description="Return the balance of one of the signed-in customer's accounts.")
async def fetch_balance(account_number: str, context: ToolContext = None) -> ToolResult:
    """Look up a single account balance.

    Args:
        account_number: The account number to read.
    """
    customer_id = context.memory.get("project.customer_id") if context else None
    if not customer_id:
        return ToolResult(llm_response={"ok": False, "error": "not_authenticated"})

    customer = customer_by_id(str(customer_id))
    account = (customer or {}).get("accounts", {}).get(account_number)
    if account is None:
        return ToolResult(
            llm_response={"ok": False, "error": "account_not_found",
                          "known_accounts": list((customer or {}).get("accounts", {}))}
        )

    if context is not None:
        context.memory.set("account_number", account_number)

    return ToolResult(
        llm_response={"ok": True, "account_number": account_number,
                      "type": account["type"], "balance": account["balance"],
                      "currency": "GBP"}
    )
