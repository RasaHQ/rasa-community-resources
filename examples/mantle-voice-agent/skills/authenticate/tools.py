"""Authenticate skill tools — local to skills/authenticate/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import DEMO_AUTH_PIN, Database, get_customer
from lib.tool_helpers import active_customer_id


@tool(description="Verify the traveler's voice PIN and mark them authenticated.")
async def verify_traveler_pin(pin: str, context: ToolContext = None) -> ToolResult:
    """Verify the traveler PIN.

    Args:
        pin: Four-digit PIN spoken or typed by the traveler.
    """
    customer_id = active_customer_id(context)
    db = Database()
    row = get_customer(db, customer_id)
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "customer_not_found"}
        )

    _cid, first_name, last_name, auth_pin = row
    cleaned = "".join(ch for ch in str(pin) if ch.isdigit())
    success = cleaned == str(auth_pin)
    if context is not None and success:
        context.memory.set("authenticated", True)

    return ToolResult(
        llm_response={
            "ok": success,
            "authenticated": success,
            "display_name": f"{first_name} {last_name}",
            "hint": (
                "PIN accepted."
                if success
                else f"PIN rejected. Demo PIN is {DEMO_AUTH_PIN}."
            ),
        }
    )
