"""Tools local to the add_payee skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, username_from_context


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
    username = username_from_context(context)
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
