"""Find-job skill tools â€” local to skills/find_job/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import PRIORITY_LABELS, Database
from lib.tool_helpers import active_tech_id


@tool(description="Look up a single task by reference or project.")
async def get_job(job_ref: str, context: ToolContext = None) -> ToolResult:
    """Look up a task.

    Args:
        job_ref: Task reference such as DEV1001.
    """
    tech_id = active_tech_id(context)
    cleaned = str(job_ref).strip().upper().replace(" ", "")
    db = Database()
    row = db.run_query(
        """
        SELECT call_ref, building, unit_id, issue, priority, status,
               scheduled_at, sla_minutes
        FROM service_calls
        WHERE tech_id = ? AND UPPER(REPLACE(call_ref, ' ', '')) = ?
        """,
        (tech_id, cleaned),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "job_not_found",
                "job_ref": cleaned,
            }
        )

    (
        call_ref_val,
        building,
        unit_id,
        issue,
        priority,
        status,
        scheduled_at,
        sla_minutes,
    ) = row

    if context is not None:
        context.memory.set("selected_job_ref", call_ref_val)
        context.memory.set("selected_project", building)

    return ToolResult(
        llm_response={
            "ok": True,
            "job": {
                "call_ref": call_ref_val,
                "project": building,
                "unit_id": unit_id,
                "issue": issue,
                "priority": priority,
                "priority_label": PRIORITY_LABELS.get(priority, priority),
                "status": status,
                "scheduled_at": scheduled_at,
                "sla_minutes": sla_minutes,
            },
        }
    )
