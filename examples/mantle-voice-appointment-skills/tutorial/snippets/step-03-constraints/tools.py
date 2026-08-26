"""Tools only the remove_contact skill uses. Auto-discovered — no import_tools."""

from __future__ import annotations

from lib.database import (
    Database,
    get_user_id,
    normalise_handle,
    username_from_context,
)
from lib.tool_helpers import set_memory
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="Remove one of the patient's saved contacts by handle.")
async def delete_contact(contact_handle: str, context: ToolContext = None) -> ToolResult:
    """Remove a contact.

    Args:
        contact_handle: Handle of the contact to remove, for example @JoeMyers.
    """
    username = username_from_context(context)
    handle = normalise_handle(contact_handle)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "patient_not_found"})

    row = db.run_query(
        "SELECT name FROM contacts WHERE user_id = ? AND lower(handle) = lower(?)",
        (user_id, handle),
        one_record=True,
    )
    if not row:
        set_memory(context, "contact_removed", False)
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "not_found",
                "contact_handle": handle,
                "hint": "No contact with that handle. Offer to list the saved contacts.",
            }
        )

    db.cursor.execute(
        "DELETE FROM contacts WHERE user_id = ? AND lower(handle) = lower(?)",
        (user_id, handle),
    )
    db.commit()

    set_memory(context, "contact_removed", True)
    set_memory(context, "contact_name", row[0])

    return ToolResult(
        llm_response={
            "ok": True,
            "contact_name": row[0],
            "contact_handle": handle,
            "removed": True,
        }
    )
