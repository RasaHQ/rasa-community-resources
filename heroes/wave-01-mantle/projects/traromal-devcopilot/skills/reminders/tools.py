"""Reminders skill tools â€” local to skills/reminders/."""

from __future__ import annotations

from datetime import datetime, timezone

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


@tool(description="Create a reminder for the developer.")
async def create_reminder(
    reminder_text: str,
    due_minutes: int = 30,
    context: ToolContext = None,
) -> ToolResult:
    """Store a personal reminder.

    Args:
        reminder_text: What to remind the developer about.
        due_minutes: Minutes from now when it becomes due.
    """
    tech_id = active_tech_id(context)
    db = Database()
    db.connection.execute(
        """
        INSERT INTO reminders
        (tech_id, reminder_text, due_minutes, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (tech_id, str(reminder_text).strip(), int(due_minutes), "open", _now()),
    )
    db.commit()
    db.save_to_disk()

    row = db.run_query(
        "SELECT MAX(id) FROM reminders", one_record=True
    )
    reminder_id = int(row[0]) if row and row[0] else 0

    return ToolResult(
        llm_response={
            "ok": True,
            "reminder_id": reminder_id,
            "reminder_text": str(reminder_text).strip(),
            "due_minutes": int(due_minutes),
        }
    )


@tool(description="List the developer's open reminders.")
async def list_reminders(context: ToolContext = None) -> ToolResult:
    """Return open reminders for the active developer."""
    tech_id = active_tech_id(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT id, reminder_text, due_minutes FROM reminders
        WHERE tech_id = ? AND status = 'open'
        ORDER BY created_at
        """,
        (tech_id,),
        one_record=False,
    )
    reminders = [
        {"reminder_id": rid, "text": text, "due_minutes": minutes}
        for (rid, text, minutes) in rows or []
    ]
    return ToolResult(
        llm_response={
            "ok": True,
            "reminders": reminders,
            "reminder_count": len(reminders),
            "tech_id": tech_id,
        }
    )
