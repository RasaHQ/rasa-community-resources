"""Shared banking tools available via import_tools."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, mask_card, resolve_username


def _username(context: Optional[ToolContext]) -> str:
    if context is None:
        return resolve_username()
    return resolve_username(context.memory.get("username"))


@tool(description="Load the demo customer profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure username / segment / contact details are available."""
    username = _username(context)
    db = Database()
    row = db.run_query(
        "SELECT name, segment, email, address FROM users WHERE name = ?",
        (username,),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "customer_not_found", "username": username}
        )

    name, segment, email, address = row
    if context is not None:
        context.memory.set("username", name)
        context.memory.set("segment", segment)
        context.memory.set("email_address", email)
        context.memory.set("physical_address", address)

    return ToolResult(
        llm_response={
            "ok": True,
            "username": name,
            "segment": segment,
            "email_address": email,
            "physical_address": address,
        }
    )


@tool(description="List the customer's bank accounts with balances.")
async def list_accounts(context: ToolContext = None) -> ToolResult:
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    rows = db.run_query(
        "SELECT number, type, balance FROM accounts WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    accounts = [
        {"account_number": number, "type": acc_type, "balance": float(balance)}
        for number, acc_type, balance in rows or []
    ]
    return ToolResult(
        llm_response={"ok": True, "accounts": accounts, "account_count": len(accounts)}
    )


@tool(description="Look up account balance by account number for the current customer.")
async def check_balance(account_number: str, context: ToolContext = None) -> ToolResult:
    """Look up account balance by account number.

    Args:
        account_number: The customer's account number (digits).
    """
    username = _username(context)
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


@tool(description="List authorised payees the customer can transfer money to.")
async def get_payees(context: ToolContext = None) -> ToolResult:
    username = _username(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT p.name, p.account_number, p.type, p.reference
        FROM payees p
        JOIN users u ON p.user_id = u.id
        WHERE u.name = ?
        """,
        (username,),
        one_record=False,
    )
    payees = [
        {
            "name": name,
            "account_number": account_number,
            "type": payee_type,
            "reference": reference,
        }
        for name, account_number, payee_type, reference in rows or []
    ]
    return ToolResult(
        llm_response={"ok": True, "payees": payees, "payee_count": len(payees)}
    )


@tool(description="Check whether a payee name already exists for the customer.")
async def check_payee_exists(payee_name: str, context: ToolContext = None) -> ToolResult:
    """Check whether a payee already exists.

    Args:
        payee_name: Payee display name to look up.
    """
    username = _username(context)
    db = Database()
    row = db.run_query(
        """
        SELECT p.id FROM payees p
        JOIN users u ON p.user_id = u.id
        WHERE u.name = ? AND lower(p.name) = lower(?)
        """,
        (username, payee_name),
        one_record=True,
    )
    exists = row is not None
    if context is not None:
        context.memory.set("payee_exists", exists)
    return ToolResult(
        llm_response={"ok": True, "payee_name": payee_name, "exists": exists}
    )


@tool(description="Add a new authorised payee for the customer.")
async def add_payee(
    payee_name: str,
    account_number: str,
    sort_code: str,
    payee_type: str,
    reference: str,
    context: ToolContext = None,
) -> ToolResult:
    """Add a payee.

    Args:
        payee_name: Display name for the payee.
        account_number: Payee account number.
        sort_code: Payee sort code.
        payee_type: person or business.
        reference: Short relationship label (friend, utilities, ...).
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    db.run_query(
        """
        INSERT INTO payees (user_id, name, sort_code, account_number, type, reference)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, payee_name, sort_code, account_number, payee_type, reference),
        one_record=False,
    )
    db.commit()
    if context is not None:
        context.memory.set("payee_added", True)
        context.memory.set("payee_name", payee_name)
    return ToolResult(
        llm_response={
            "ok": True,
            "payee_name": payee_name,
            "account_number": account_number,
            "sort_code": sort_code,
            "payee_type": payee_type,
            "reference": reference,
        }
    )


@tool(description="Remove an authorised payee by name.")
async def remove_payee(payee_name: str, context: ToolContext = None) -> ToolResult:
    """Remove a payee by name.

    Args:
        payee_name: Payee to remove.
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    db.cursor.execute(
        "DELETE FROM payees WHERE user_id = ? AND lower(name) = lower(?)",
        (user_id, payee_name),
    )
    deleted = db.cursor.rowcount
    db.commit()
    if context is not None:
        context.memory.set("payee_removed", deleted > 0)
    return ToolResult(
        llm_response={
            "ok": deleted > 0,
            "payee_name": payee_name,
            "removed": deleted > 0,
        }
    )


@tool(description="Check whether the source account has enough funds for a transfer.")
async def check_sufficient_funds(
    account_number: str, amount: float, context: ToolContext = None
) -> ToolResult:
    """Validate funds.

    Args:
        account_number: Source account number.
        amount: Transfer amount.
    """
    username = _username(context)
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
    username = _username(context)
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


@tool(description="List the customer's active bank cards.")
async def list_cards(context: ToolContext = None) -> ToolResult:
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    rows = db.run_query(
        "SELECT number, type, status FROM cards WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    cards = [
        {
            "card_number": number,
            "masked": mask_card(number),
            "type": card_type,
            "status": status,
        }
        for number, card_type, status in rows or []
    ]
    if context is not None:
        context.memory.set("cards_loaded", True)
    return ToolResult(llm_response={"ok": True, "cards": cards, "card_count": len(cards)})


@tool(description="Block or freeze a card so it cannot be used.")
async def block_card(card_number: str, context: ToolContext = None) -> ToolResult:
    """Block a card.

    Args:
        card_number: Full card number to block.
    """
    username = _username(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    db.cursor.execute(
        """
        UPDATE cards
        SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
        WHERE number = ? AND user_id = ?
        """,
        (card_number, user_id),
    )
    updated = db.cursor.rowcount
    db.commit()
    if updated == 0:
        return ToolResult(
            llm_response={"ok": False, "error": "card_not_found", "card_number": card_number}
        )

    if context is not None:
        context.memory.set("card_blocked", True)
        context.memory.set("selected_card_id", card_number)
        context.memory.set("selected_card_label", mask_card(card_number))

    return ToolResult(
        llm_response={
            "ok": True,
            "card_number": card_number,
            "masked": mask_card(card_number),
            "status": "inactive",
        }
    )


@tool(description="Request a replacement card to be shipped to the customer's address.")
async def order_replacement_card(
    card_number: str, shipping: str = "standard", context: ToolContext = None
) -> ToolResult:
    """Order a replacement card.

    Args:
        card_number: Card being replaced.
        shipping: standard or express.
    """
    username = _username(context)
    db = Database()
    row = db.run_query(
        "SELECT address FROM users WHERE name = ?", (username,), one_record=True
    )
    address = row[0] if row else "address on file"
    reference = f"CARD-{card_number[-4:]}-{shipping[:3].upper()}"
    if context is not None:
        context.memory.set("replacement_ordered", True)
        context.memory.set("shipping_type", shipping)
    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "shipping": shipping,
            "ship_to": address,
            "masked_card": mask_card(card_number),
        }
    )


@tool(description="Create a human handoff ticket for a live agent.")
async def create_handoff_ticket(reason: str, context: ToolContext = None) -> ToolResult:
    """Create a handoff ticket.

    Args:
        reason: Why the customer wants a human agent.
    """
    ticket_id = f"HO-{datetime.utcnow().strftime('%H%M%S')}"
    if context is not None:
        context.memory.set("handoff_created", True)
        context.memory.set("handoff_ticket_id", ticket_id)
    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "eta_minutes": 5,
        }
    )
