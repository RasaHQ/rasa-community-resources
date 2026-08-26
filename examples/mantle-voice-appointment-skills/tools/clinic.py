"""Tools shared by two or more skills, pulled in with ``import_tools``.

Anything used by a single skill lives in that skill's own ``skills/<id>/tools.py``
and is auto-discovered there. Only genuinely shared behaviour belongs here:

- ``load_customer_profile`` — run by ``default_session_start``, and available as
  a mid-session fallback wherever the username may be missing
- ``get_contacts`` — ``list_contacts``, ``add_contact``, and ``remove_contact``

Tool names deliberately differ from skill names. A tool called ``list_contacts``
alongside a skill called ``list_contacts`` makes prose like "call list_contacts"
ambiguous, so the reader is ``get_contacts`` and the writers are
``save_contact`` / ``delete_contact``.
"""

from __future__ import annotations

from lib.database import Database, username_from_context
from lib.tool_helpers import set_memory
from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult


@tool(description="Load the demo patient profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure username / patient id / contact details are available."""
    username = username_from_context(context)
    db = Database()
    row = db.run_query(
        "SELECT name, patient_id, email, phone FROM users WHERE name = ?",
        (username,),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "patient_not_found", "username": username}
        )

    name, patient_id, email, phone = row
    set_memory(context, "username", name)
    set_memory(context, "patient_id", patient_id)
    set_memory(context, "email", email)
    set_memory(context, "phone", phone)

    return ToolResult(
        llm_response={
            "ok": True,
            "username": name,
            "patient_id": patient_id,
            "email": email,
            "phone": phone,
        }
    )


@tool(description="List the patient's saved contacts with their handles.")
async def get_contacts(context: ToolContext = None) -> ToolResult:
    username = username_from_context(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT c.name, c.handle, c.relationship
        FROM contacts c
        JOIN users u ON c.user_id = u.id
        WHERE u.name = ?
        ORDER BY c.name
        """,
        (username,),
        one_record=False,
    )
    contacts = [
        {"name": name, "handle": handle, "relationship": relationship}
        for name, handle, relationship in rows or []
    ]
    return ToolResult(
        llm_response={"ok": True, "contacts": contacts, "contact_count": len(contacts)}
    )
