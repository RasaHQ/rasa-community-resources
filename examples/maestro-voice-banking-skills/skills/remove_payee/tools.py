"""Tools local to the remove_payee skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_user_id, username_from_context


@tool(description="Remove an authorised payee by name.")
async def remove_payee(payee_name: str, context: ToolContext = None) -> ToolResult:
    """Remove a payee by name.

    Args:
        payee_name: Payee to remove.
    """
    username = username_from_context(context)
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
