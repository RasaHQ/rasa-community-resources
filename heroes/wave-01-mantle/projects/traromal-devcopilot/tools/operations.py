"""Shared operations tools â€” only helpers used by more than one skill.

Skill-owned tools live in skills/<name>/tools.py and are auto-discovered.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import PRIORITY_LABELS, Database, get_technician, resolve_tech_id
from lib.tool_helpers import active_tech_id, tech_display_name


@tool(description="Load the active developer profile into project memory.")
async def load_developer_profile(
    tech_id: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Ensure tech_id / name fields are available.

    Args:
        tech_id: Optional developer id. The demo always resolves to Alex
            Chen (101) when omitted or unrecognized.
    """
    requested = resolve_tech_id(tech_id) if tech_id else active_tech_id(context)
    db = Database()
    row = get_technician(db, requested)
    if not row:
        row = get_technician(db, resolve_tech_id())
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "developer_not_found",
                "tech_id": requested,
            }
        )

    tid, first_name, last_name, _badge = row
    if context is not None:
        context.memory.set("tech_id", tid)
        context.memory.set("tech_first_name", first_name)
        context.memory.set("tech_last_name", last_name)

    return ToolResult(
        llm_response={
            "ok": True,
            "tech_id": tid,
            "tech_first_name": first_name,
            "tech_last_name": last_name,
            "display_name": f"{first_name} {last_name}",
        }
    )


@tool(description="List the developer's open tasks and SLA status.")
async def list_jobs(context: ToolContext = None) -> ToolResult:
    tech_id = active_tech_id(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT call_ref, building, unit_id, issue, priority, status,
               scheduled_at, sla_minutes
        FROM service_calls
        WHERE tech_id = ? AND status != 'closed'
        ORDER BY CASE priority WHEN 'emergency' THEN 0 WHEN 'standard' THEN 1
                 ELSE 2 END, scheduled_at
        """,
        (tech_id,),
        one_record=False,
    )
    jobs = [
        {
            "call_ref": call_ref,
            "project": building,
            "unit_id": unit_id,
            "issue": issue,
            "priority": priority,
            "priority_label": PRIORITY_LABELS.get(priority, priority),
            "status": status,
            "scheduled_at": scheduled_at,
            "sla_minutes": sla_minutes,
        }
        for (
            call_ref,
            building,
            unit_id,
            issue,
            priority,
            status,
            scheduled_at,
            sla_minutes,
        ) in rows
        or []
    ]
    has_emergency = any(job["priority"] == "emergency" for job in jobs)
    display_name = tech_display_name(context)
    if not display_name:
        tech = get_technician(db, tech_id)
        if tech:
            display_name = f"{tech[1]} {tech[2]}"

    return ToolResult(
        llm_response={
            "ok": True,
            "jobs": jobs,
            "job_count": len(jobs),
            "has_emergency": has_emergency,
            "tech_id": tech_id,
            "display_name": display_name,
        }
    )
