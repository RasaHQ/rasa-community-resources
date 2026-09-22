"""Mock account and transaction lookup for the view_transactions skill.

Demonstrates a downstream skill *reusing* identity seeded at session start: the
skill's prose reads session.project.customer_name / default_account_* to greet
by name and offer the usual account first, without any lookup of its own.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

# Two fictional demo accounts for the select-account flow. acc_checking matches
# the default_account_id seeded by the session-start profile lookup.
_ACCOUNTS = [
    {"id": "acc_checking", "label": "Everyday Checking", "last_four": "4821"},
    {"id": "acc_savings", "label": "Rainy Day Savings", "last_four": "7390"},
]

_TRANSACTIONS_BY_ACCOUNT: dict[str, list[dict[str, str]]] = {
    "acc_checking": [
        {"id": "txn_c001", "date": "2026-07-28", "merchant": "Blue Harbor Market", "amount": "-$42.18"},
        {"id": "txn_c002", "date": "2026-07-26", "merchant": "Northline Transit", "amount": "-$3.50"},
        {"id": "txn_c003", "date": "2026-07-24", "merchant": "Cedar & Co.", "amount": "-$68.00"},
        {"id": "txn_c004", "date": "2026-07-22", "merchant": "Payroll Deposit", "amount": "+$2,150.00"},
    ],
    "acc_savings": [
        {"id": "txn_s001", "date": "2026-07-20", "merchant": "Interest Credit", "amount": "+$12.44"},
        {"id": "txn_s002", "date": "2026-07-01", "merchant": "Transfer from Checking", "amount": "+$200.00"},
        {"id": "txn_s003", "date": "2026-06-15", "merchant": "Summit Utilities Autopay", "amount": "-$85.00"},
    ],
}


@tool(description="Load the customer's accounts. Call this before asking which one.")
async def fetch_accounts(context: ToolContext = None) -> ToolResult:
    """Return the two mock accounts available for selection."""
    return ToolResult(
        llm_response={"accounts": _ACCOUNTS, "account_count": len(_ACCOUNTS)}
    )


@tool(
    description=(
        "Return recent transactions for the selected account. Call only after "
        "selected_account_id is set in skill memory."
    )
)
async def get_recent_transactions(context: ToolContext = None) -> ToolResult:
    """Return mock transactions for the account stored in skill memory."""
    if context is None:
        return ToolResult(
            llm_response={"ok": False, "error": "no_context", "hint": "Tool requires a runtime context."}
        )

    account_id = context.memory.get("selected_account_id")
    if not account_id:
        return ToolResult(
            llm_response={"ok": False, "error": "no_account_selected", "hint": "Select an account first."}
        )

    account = next((item for item in _ACCOUNTS if item["id"] == str(account_id)), None)
    transactions = _TRANSACTIONS_BY_ACCOUNT.get(str(account_id))
    if account is None or transactions is None:
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
            "transactions": transactions,
            "transaction_count": len(transactions),
        }
    )
