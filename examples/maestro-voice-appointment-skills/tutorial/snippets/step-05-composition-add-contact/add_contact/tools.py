"""Tools only the add_contact skill uses. Auto-discovered — no import_tools."""

from __future__ import annotations

from lib.database import (
    Database,
    get_user_id,
    normalise_handle,
    username_from_context,
)
from lib.tool_helpers import set_memory
from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult


@tool(description="Save a new contact for the patient using their name and handle.")
async def save_contact(
    contact_name: str,
    contact_handle: str,
    relationship: str = "contact",
    context: ToolContext = None,
) -> ToolResult:
    """Add a contact.

    Args:
        contact_name: Display name for the contact, for example Joe.
        contact_handle: The contact's handle, for example @JoeMyers.
        relationship: Short label such as friend, sister, or doctor.
    """
    username = username_from_context(context)
    handle = normalise_handle(contact_handle)
    if not contact_name or not handle:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "missing_details",
                "hint": "Both a name and a handle are needed before saving a contact.",
            }
        )

    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "patient_not_found"})

    existing = db.run_query(
        """
        SELECT name, handle FROM contacts
        WHERE user_id = ? AND (lower(handle) = lower(?) OR lower(name) = lower(?))
        """,
        (user_id, handle, contact_name),
        one_record=True,
    )
    if existing:
        set_memory(context, "contact_exists", True)
        set_memory(context, "contact_added", False)
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "duplicate_contact",
                "contact_name": existing[0],
                "contact_handle": existing[1],
                "hint": "This contact is already saved. Do not add it a second time.",
            }
        )

    db.run_query(
        "INSERT INTO contacts (user_id, name, handle, relationship) VALUES (?, ?, ?, ?)",
        (user_id, contact_name, handle, relationship),
        one_record=False,
    )
    db.commit()

    set_memory(context, "contact_exists", False)
    set_memory(context, "contact_added", True)
    set_memory(context, "contact_name", contact_name)
    set_memory(context, "contact_handle", handle)

    return ToolResult(
        llm_response={
            "ok": True,
            "contact_name": contact_name,
            "contact_handle": handle,
            "relationship": relationship,
        }
    )
