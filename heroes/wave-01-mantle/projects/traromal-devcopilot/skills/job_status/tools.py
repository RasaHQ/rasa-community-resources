"""Job-status skill tools â€” local to skills/job_status/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import PRIORITY_LABELS, Database


@tool(description="Get SLA status and priority for a task.")
async def get_job_status(
    job_ref: str, context: ToolContext = None
) -> ToolResult:
    """Return the task with its SLA window.

    Args:
        job_ref: Task reference such as DEV1001.
    """
    cleaned = str(job_ref).strip().upper().replace(" ", "")
    db = Database()
    row = db.run_query(
        """
        SELECT call_ref, building, unit_id, issue, priority, status,
               scheduled_at, sla_minutes
        FROM service_calls WHERE UPPER(REPLACE(call_ref, ' ', '')) = ?
        """,
        (cleaned,),
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
        context.memory.set("job_ref", cleaned)
        context.memory.set("priority", priority)

    return ToolResult(
        llm_response={
            "ok": True,
            "job_ref": cleaned,
            "project": building,
            "unit_id": unit_id,
            "issue": issue,
            "priority": priority,
            "priority_label": PRIORITY_LABELS.get(priority, priority),
            "status": status,
            "scheduled_at": scheduled_at,
            "sla_minutes": sla_minutes,
        }
    )
