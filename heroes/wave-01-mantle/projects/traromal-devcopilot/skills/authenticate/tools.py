"""Authenticate skill tools â€” local to skills/authenticate/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import DEMO_BADGE_CODE, Database, get_technician
from lib.tool_helpers import active_tech_id


@tool(description="Verify the developer's badge code and mark them authenticated.")
async def verify_badge(badge_code: str = "", context: ToolContext = None) -> ToolResult:
    """Verify the developer badge code.

    Args:
        badge_code: Four-digit badge code spoken or typed by the developer.
    """
    tech_id = active_tech_id(context)
    db = Database()
    row = get_technician(db, tech_id)
    if not row:
        return ToolResult(llm_response={"ok": False, "error": "developer_not_found"})

    _tid, first_name, last_name, badge = row
    raw = "" if badge_code is None else str(badge_code)
    if not raw.strip() and context is not None:
        raw = context.memory.get("badge_attempt") or ""
    cleaned = "".join(ch for ch in raw if ch.isdigit())
    success = cleaned == str(badge)
    if context is not None and success:
        context.memory.set("authenticated", True)

    return ToolResult(
        llm_response={
            "ok": success,
            "authenticated": success,
            "display_name": f"{first_name} {last_name}",
            "hint": (
                "Badge accepted."
                if success
                else f"Badge rejected. Demo badge is {DEMO_BADGE_CODE}."
            ),
        }
    )
