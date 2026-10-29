"""Job-close skill tools â€” local to skills/job_close/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, get_part
from lib.tool_helpers import active_tech_id


@tool(description="Close a completed task and log tools or licenses used.")
async def close_work_order(
    job_ref: str,
    diagnosis: str,
    resolution: str,
    labor_hours: str,
    part_no: str,
    context: ToolContext = None,
) -> ToolResult:
    """Close a task after the developer has confirmed.

    Args:
        job_ref: Task reference being closed.
        diagnosis: Short summary of what was found and done.
        resolution: fixed, replaced_component, no_issue, or deferred.
        labor_hours: Hours spent on the task.
        part_no: Tool or license used, or none.
    """
    tech_id = active_tech_id(context)
    cleaned_ref = str(job_ref).strip().upper().replace(" ", "")
    db = Database()

    row = db.run_query(
        """
        SELECT call_ref, building, priority, status FROM service_calls
        WHERE tech_id = ? AND UPPER(REPLACE(call_ref, ' ', '')) = ?
        """,
        (tech_id, cleaned_ref),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "job_not_found", "job_ref": cleaned_ref}
        )

    call_ref_val, building, priority, status = row
    if status == "closed":
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "already_closed",
                "job_ref": call_ref_val,
            }
        )

    # Consume part stock when a part was logged. Missing or out-of-stock parts
    # still close the WO but flag stock for a follow-up order.
    consumed_part = None
    if part_no and str(part_no).strip().lower() not in ("none", "no", "n/a"):
        part_details = get_part(db, str(part_no))
        if part_details and part_details[3] and part_details[3] > 0:
            db.connection.execute(
                "UPDATE parts SET qty_on_hand = qty_on_hand - 1 WHERE part_no = ?",
                (part_details[0],),
            )
            db.commit()
            consumed_part = part_details[0]

    db.connection.execute(
        "UPDATE service_calls SET status = ? WHERE call_ref = ?",
        ("closed", call_ref_val),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("details_verified", True)
        context.memory.set("closed_job_ref", call_ref_val)

    return ToolResult(
        llm_response={
            "ok": True,
            "job_ref": call_ref_val,
            "project": building,
            "priority": priority,
            "status": "closed",
            "diagnosis": str(diagnosis).strip(),
            "resolution": str(resolution).strip(),
            "labor_hours": str(labor_hours).strip(),
            "part_no": consumed_part or str(part_no).strip(),
            "part_consumed": bool(consumed_part),
        }
    )
