"""Shared banking tools used by several skills (and by session start).

Skill-specific tools live next to their skill in ``skills/<name>/tools.py`` and
are auto-discovered — they do not need ``import_tools``. Only tools reused across
two or more skills belong here; a skill pulls them in with ``import_tools``.
"""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, username_from_context


@tool(description="Load the demo customer profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure username / segment / contact details are available.

    Runs deterministically at session start (via the session-start ordered
    block) so identity is in project memory before any skill activates.
    """
    username = username_from_context(context)
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
    username = username_from_context(context)
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


@tool(description="List authorised payees the customer can transfer money to.")
async def get_payees(context: ToolContext = None) -> ToolResult:
    username = username_from_context(context)
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
    username = username_from_context(context)
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
