"""Deterministic account and balance lookups for the fixture agent.

Every value here is hard-coded on purpose. An evaluation harness can only
measure the agent if the data underneath it does not move: when a
`slot_was_set` or `bot_uttered` assertion fails, you want that to mean the
agent changed, never that the fixture returned a different row this time.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

_ACCOUNTS = [
    {"id": "acc_checking", "label": "Everyday Checking", "last_four": "4821"},
    {"id": "acc_savings", "label": "Rainy Day Savings", "last_four": "7390"},
]

_BALANCES = {
    "acc_checking": "$1,284.53",
    "acc_savings": "$9,140.00",
}


@tool(description="Load the customer's accounts. Call this before asking which one.")
async def fetch_accounts(context: ToolContext = None) -> ToolResult:
    """Return the two fixed demo accounts available for selection."""
    return ToolResult(
        llm_response={"accounts": _ACCOUNTS, "account_count": len(_ACCOUNTS)}
    )


@tool(
    description=(
        "Return the balance of the selected account. Call only after "
        "selected_account_id is set in skill memory."
    )
)
async def get_balance(context: ToolContext = None) -> ToolResult:
    """Return the fixed balance for the account stored in skill memory."""
    if context is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_context",
                "hint": "Tool requires a runtime context.",
            }
        )

    account_id = str(context.memory.get("selected_account_id") or "")
    account = next((item for item in _ACCOUNTS if item["id"] == account_id), None)

    if account is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unknown_account",
                "account_id": account_id,
                "hint": "Ask the customer to pick Everyday Checking or Rainy Day Savings.",
            }
        )

    context.memory.set("selected_account_label", account["label"])
    return ToolResult(
        llm_response={
            "ok": True,
            "account_id": account_id,
            "account_label": account["label"],
            "balance": _BALANCES[account_id],
        }
    )
