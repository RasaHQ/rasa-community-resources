"""Beta-feedback tools for recording assistant behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id

_CATEGORIES = {"bug", "usability", "safety", "voice", "feature"}
_SEVERITIES = {"critical", "high", "medium", "low"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


@tool(description="Record beta feedback about DevPilot.")
async def record_feedback(category: str, severity: str, description: str, expected: str, actual: str, context: ToolContext = None) -> ToolResult:
    category = str(category).strip().lower()
    severity = str(severity).strip().lower()
    if category not in _CATEGORIES or severity not in _SEVERITIES:
        return ToolResult(llm_response={"ok": False, "error": "invalid_category_or_severity"})
    db = Database()
    db.connection.execute(
        """INSERT INTO feedback
        (tech_id, category, severity, description, expected, actual, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (active_tech_id(context), category, severity, str(description).strip(), str(expected).strip(), str(actual).strip(), _now(), "open"),
    )
    db.commit()
    db.save_to_disk()
    row = db.run_query("SELECT id FROM feedback ORDER BY id DESC LIMIT 1", one_record=True)
    feedback_id = f"FB{row[0]:04d}" if row else "FB0000"
    return ToolResult(llm_response={"ok": True, "feedback_id": feedback_id, "category": category, "severity": severity})


@tool(description="List recent beta feedback about DevPilot.")
async def list_feedback(context: ToolContext = None) -> ToolResult:
    db = Database()
    rows = db.run_query(
        """SELECT id, category, severity, description, expected, actual, created_at, status
        FROM feedback WHERE tech_id = ? ORDER BY id DESC LIMIT 25""",
        (active_tech_id(context),), one_record=False,
    ) or []
    return ToolResult(llm_response={
        "ok": True,
        "feedback": [{"feedback_id": f"FB{r[0]:04d}", "category": r[1], "severity": r[2], "description": r[3], "expected": r[4], "actual": r[5], "created_at": r[6], "status": r[7]} for r in rows],
    })
