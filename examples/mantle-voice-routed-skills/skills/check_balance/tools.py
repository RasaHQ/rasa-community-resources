"""Tools local to the check_balance skill (auto-discovered)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.bank import get_account


@tool(
    description=(
        "Look up the balance of the caller's checking or savings account. "
        "Accepts the account name as the caller said it."
    )
)
async def check_balance(account_type: str, context: ToolContext = None) -> ToolResult:
    """Return the balance for a spoken account name.

    Args:
        account_type: The account as the caller said it ("checking", "my
            current one", "savings"). Normalised inside the tool.
    """
    key, account = get_account(account_type)
    if key is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unknown_account",
                "heard": account_type,
                "hint": "Ask whether they mean checking or savings.",
            }
        )

    if context is not None:
        context.memory.set("account_type", key)
        context.memory.set("account_balance", float(account["balance"]))

    return ToolResult(
        llm_response={
            "ok": True,
            "account_type": key,
            "account_label": account["label"],
            "balance": float(account["balance"]),
            "currency": "USD",
        }
    )
