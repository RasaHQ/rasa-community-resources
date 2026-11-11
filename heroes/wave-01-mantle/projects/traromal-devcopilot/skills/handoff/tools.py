"""On-call handoff skill tools â€” local to skills/handoff/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@tool(description="Build an end-of-shift on-call handoff summary.")
async def get_handoff_summary(context: ToolContext = None) -> ToolResult:
    """Collect open risk, active work, pending approvals, and last deploy."""
    tech_id = active_tech_id(context)
    db = Database()

    ticket_rows = db.run_query(
        """
        SELECT ticket_id, summary, severity, system, status
        FROM support_tickets
        WHERE tech_id = ? AND status != 'done'
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                 WHEN 'medium' THEN 2 ELSE 3 END
        """,
        (tech_id,),
        one_record=False,
    )
    open_tickets = [
        {
            "ticket_id": tid,
            "summary": summary,
            "severity": severity,
            "system": system,
            "status": status,
        }
        for (tid, summary, severity, system, status) in ticket_rows or []
    ]
    hot = [
        t for t in open_tickets if _SEVERITY_ORDER.get(t["severity"], 9) <= 1
    ]

    approval_rows = db.run_query(
        """
        SELECT order_id, part_no, qty FROM parts_orders
        WHERE tech_id = ? AND status = 'pending_approval'
        """,
        (tech_id,),
        one_record=False,
    )
    pending_approvals = [
        {"order_id": oid, "part_no": part_no, "qty": qty}
        for (oid, part_no, qty) in approval_rows or []
    ]

    last_deploy_row = db.run_query(
        """
        SELECT project, environment, deploy_ref, deployed_at
        FROM deployments ORDER BY deployed_at DESC LIMIT 1
        """,
        one_record=True,
    )
    if last_deploy_row:
        project, environment, deploy_ref, deployed_at = last_deploy_row
        last_deploy = {
            "project": project,
            "environment": environment,
            "deploy_ref": deploy_ref,
            "deployed_at": deployed_at,
        }
    else:
        last_deploy = None

    return ToolResult(
        llm_response={
            "ok": True,
            "hot_items": hot,
            "hot_count": len(hot),
            "open_count": len(open_tickets),
            "open_tickets": open_tickets,
            "pending_approvals": pending_approvals,
            "pending_approval_count": len(pending_approvals),
            "last_deployment": last_deploy,
            "tech_id": tech_id,
        }
    )
