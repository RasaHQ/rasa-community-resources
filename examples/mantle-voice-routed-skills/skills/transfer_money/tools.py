"""Tools local to the transfer_money skill (auto-discovered)."""

from __future__ import annotations

import random
import string

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.bank import ACCOUNTS, get_account


@tool(
    description=(
        "Check that a transfer is possible: both accounts resolve, they differ, "
        "and the source holds enough. Call before confirming with the caller."
    )
)
async def check_transfer(
    from_account: str,
    to_account: str,
    amount: float,
    context: ToolContext = None,
) -> ToolResult:
    """Validate a transfer without moving anything.

    Args:
        from_account: Source account as the caller said it.
        to_account: Destination account as the caller said it.
        amount: Amount in dollars.
    """
    src_key, src = get_account(from_account)
    dst_key, _ = get_account(to_account)

    if src_key is None or dst_key is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unknown_account",
                "heard_from": from_account,
                "heard_to": to_account,
                "hint": "Both accounts must be checking or savings.",
            }
        )
    if src_key == dst_key:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "same_account",
                "hint": "Source and destination must be different accounts.",
            }
        )
    if amount is None or amount <= 0:
        return ToolResult(
            llm_response={"ok": False, "error": "invalid_amount", "amount": amount}
        )

    enough = float(amount) <= float(src["balance"])
    if context is not None:
        context.memory.set("from_account", src_key)
        context.memory.set("to_account", dst_key)
        context.memory.set("amount", float(amount))
        context.memory.set("sufficient_funds", enough)

    return ToolResult(
        llm_response={
            "ok": True,
            "from_account": src_key,
            "to_account": dst_key,
            "amount": float(amount),
            "source_balance": float(src["balance"]),
            "sufficient_funds": enough,
        }
    )


@tool(
    description=(
        "Move the money. Call only after the caller has confirmed the details "
        "read back to them."
    )
)
async def process_transfer(context: ToolContext = None) -> ToolResult:
    """Apply a validated transfer to the in-memory demo accounts."""
    if context is None:
        return ToolResult(llm_response={"ok": False, "error": "no_context"})

    src_key = context.memory.get("from_account")
    dst_key = context.memory.get("to_account")
    amount = context.memory.get("amount")

    if not src_key or not dst_key or not amount:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "incomplete_transfer",
                "hint": "Collect both accounts and the amount, then call check_transfer.",
            }
        )
    if float(amount) > float(ACCOUNTS[src_key]["balance"]):
        # Re-checked here on purpose: the balance is the authority at the moment
        # of the write, not whatever was true when the caller was asked.
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "insufficient_funds",
                "balance": float(ACCOUNTS[src_key]["balance"]),
            }
        )

    ACCOUNTS[src_key]["balance"] -= float(amount)
    ACCOUNTS[dst_key]["balance"] += float(amount)
    reference = "NW" + "".join(random.choices(string.digits, k=6))
    context.memory.set("transfer_reference", reference)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "from_account": src_key,
            "to_account": dst_key,
            "amount": float(amount),
            "new_source_balance": float(ACCOUNTS[src_key]["balance"]),
        }
    )
