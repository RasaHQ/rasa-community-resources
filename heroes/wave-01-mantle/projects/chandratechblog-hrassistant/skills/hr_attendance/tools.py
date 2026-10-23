"""Attendance lookup for the HR assistant."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

ATTENDANCE_RECORDS: dict[str, dict[str, str]] = {
    "E1001|2026-09-10": {
        "recorded_hours": "8.0",
        "status": "Present",
        "next_step": "No action is currently recorded.",
    },
    "E1001|2026-09-11": {
        "recorded_hours": "Missing clock-out",
        "status": "Correction needed",
        "next_step": "Submit an attendance correction or contact your manager.",
    },
}


@tool(description="Look up an employee attendance record for a specific date.")
async def lookup_attendance(
    employee_id: str,
    attendance_date: str,
    context: ToolContext = None,
) -> ToolResult:
    """Return a configured attendance record or a not-found response."""
    record = ATTENDANCE_RECORDS.get(f"{employee_id.upper()}|{attendance_date}")
    if record is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "found": False,
                "employee_id": employee_id,
                "attendance_date": attendance_date,
            }
        )
    return ToolResult(
        llm_response={
            "ok": True,
            "found": True,
            "demo": True,
            "employee_id": employee_id.upper(),
            "attendance_date": attendance_date,
            **record,
        }
    )
