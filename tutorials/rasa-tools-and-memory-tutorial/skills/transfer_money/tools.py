"""LOCAL tool for transfer_money — moving money is this skill's workflow."""

from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool

from lib.directory import customer_by_id


@tool(description="Send money from the signed-in customer to a known payee.")
async def make_transfer(
    payee_name: str, amount: float, context: ToolContext = None
) -> ToolResult:
    """Move money to an authorised payee.

    Args:
        payee_name: Name of an existing payee.
        amount: Amount to send, in GBP.
    """
    customer_id = context.memory.get("project.customer_id") if context else None
    if not customer_id:
        return ToolResult(llm_response={"ok": False, "error": "not_authenticated"})

    customer = customer_by_id(str(customer_id)) or {}
    account_number = customer.get("payees", {}).get(payee_name)
    if account_number is None:
        return ToolResult(
            llm_response={"ok": False, "error": "payee_not_found",
                          "known_payees": list(customer.get("payees", {}))}
        )

    return ToolResult(
        llm_response={"ok": True, "payee_name": payee_name,
                      "account_number": account_number,
                      "amount": float(amount), "currency": "GBP"}
    )
