"""Tools local to the transaction_history skill (auto-discovered)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.bank import TRANSACTIONS


@tool(description="Return the caller's recent transactions, most recent first.")
async def get_transactions(context: ToolContext = None) -> ToolResult:
    """Return the seeded demo transactions."""
    rows = sorted(TRANSACTIONS, key=lambda t: t["date"], reverse=True)
    return ToolResult(
        llm_response={
            "ok": True,
            "transactions": rows,
            "transaction_count": len(rows),
        }
    )
