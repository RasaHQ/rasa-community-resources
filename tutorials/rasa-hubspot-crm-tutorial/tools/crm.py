"""GLOBAL tools — the CRM lookup every skill depends on.

`find_contact_by_email` is global because it passes all three tests: more than
one skill needs it, it is skill-agnostic, and it is about the end user rather
than one workflow. It lives at the project root and each skill names it in
`import_tools`.

Note what it returns on failure. A CRM that cannot be reached and a customer who
is not in the CRM are different facts, and the agent must be able to say which
one happened rather than guessing.
"""

from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool
from lib.hubspot import CrmError, find_contact_by_email as _find


@tool(
    description=(
        "Find the customer in the CRM by their email address. "
        "Call this before discussing anything about their account."
    )
)
async def find_contact_by_email(
    email: str, context: ToolContext = None
) -> ToolResult:
    """Look the caller up in HubSpot.

    Args:
        email: The customer's email address.
    """
    try:
        contact = await _find(email)
    except CrmError as exc:
        return ToolResult(llm_response={"ok": False, "error": exc.reason})

    if contact is None:
        # Not an error: the CRM answered, and nobody matches.
        return ToolResult(llm_response={"ok": False, "error": "contact_not_found", "email": email})

    if context is not None:
        context.memory.set("contact_id", contact.id)
        context.memory.set("contact_email", contact.email)
        context.memory.set("contact_name", contact.full_name)

    return ToolResult(
        llm_response={
            "ok": True,
            "contact_id": contact.id,
            "name": contact.full_name,
            "company": contact.company,
        }
    )
