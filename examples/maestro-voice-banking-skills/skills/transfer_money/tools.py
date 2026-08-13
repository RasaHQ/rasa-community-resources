"""Tools local to the transfer_money skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from datetime import datetime

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, username_from_context


@tool(description="Check whether the source account has enough funds for a transfer.")
async def check_sufficient_funds(
    account_number: str, amount: float, context: ToolContext = None
) -> ToolResult:
    """Validate funds.

    Args:
        account_number: Source account number.
        amount: Transfer amount.
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    row = db.run_query(
        "SELECT balance FROM accounts WHERE user_id = ? AND number = ?",
        (user_id, account_number),
        one_record=True,
    )
    if not row:
        return ToolResult(llm_response={"ok": False, "error": "account_not_found"})

    balance = float(row[0])
    sufficient = amount > 0 and balance >= amount
    if context is not None:
        context.memory.set("sufficient_funds", sufficient)
        context.memory.set("account_balance", balance)
    return ToolResult(
        llm_response={
            "ok": True,
            "sufficient": sufficient,
            "balance": balance,
            "amount": amount,
        }
    )


@tool(description="Process an immediate money transfer to an authorised payee.")
async def process_transfer(
    account_number: str,
    payee_name: str,
    amount: float,
    context: ToolContext = None,
) -> ToolResult:
    """Process an immediate transfer.

    Args:
        account_number: Source account number.
        payee_name: Destination payee name.
        amount: Amount to transfer.
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    row = db.run_query(
        "SELECT id, balance FROM accounts WHERE user_id = ? AND number = ?",
        (user_id, account_number),
        one_record=True,
    )
    if not row:
        return ToolResult(llm_response={"ok": False, "error": "account_not_found"})

    account_id, balance = int(row[0]), float(row[1])
    if amount <= 0 or balance < amount:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "insufficient_funds",
                "balance": balance,
                "amount": amount,
            }
        )

    new_balance = balance - amount
    db.cursor.execute(
        "UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id)
    )
    db.cursor.execute(
        """
        INSERT INTO transactions (account_id, amount, datetime, description, payment_method, payee)
        VALUES (?, ?, datetime('now'), ?, 'transfer', ?)
        """,
        (account_id, -amount, f"Transfer to {payee_name}", payee_name),
    )
    db.commit()

    reference = f"TX-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    if context is not None:
        context.memory.set("payment_processed", True)
        context.memory.set("transfer_reference", reference)
        context.memory.set("account_balance", new_balance)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "payee_name": payee_name,
            "amount": amount,
            "new_balance": new_balance,
        }
    )


@tool(description="Schedule a future money transfer for a given date (YYYY-MM-DD).")
async def schedule_transfer(
    account_number: str,
    payee_name: str,
    amount: float,
    payment_date: str,
    context: ToolContext = None,
) -> ToolResult:
    """Schedule a transfer.

    Args:
        account_number: Source account number.
        payee_name: Destination payee name.
        amount: Amount to transfer.
        payment_date: Future date in YYYY-MM-DD format.
    """
    try:
        scheduled = datetime.strptime(payment_date, "%Y-%m-%d").date()
    except ValueError:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_date",
                "hint": "Use YYYY-MM-DD for the payment date.",
            }
        )

    if scheduled <= datetime.utcnow().date():
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "date_not_in_future",
                "hint": "Choose a future date for a scheduled payment.",
            }
        )

    reference = f"SCH-{scheduled.strftime('%Y%m%d')}-{int(amount)}"
    if context is not None:
        context.memory.set("payment_scheduled", True)
        context.memory.set("transfer_reference", reference)
        context.memory.set("payment_date", payment_date)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "payee_name": payee_name,
            "amount": amount,
            "payment_date": payment_date,
            "account_number": account_number,
        }
    )
