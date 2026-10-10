"""Cross-system engineering briefing tools."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id


@tool(description="Build a cross-system engineering briefing for the active developer.")
async def get_engineering_briefing(context: ToolContext = None) -> ToolResult:
    """Return urgent work, review queue, approvals, reminders, and deploy state."""
    tech_id = active_tech_id(context)
    db = Database()

    tickets = db.run_query(
        """
        SELECT ticket_id, summary, severity, system, status
        FROM support_tickets
        WHERE tech_id = ? AND status != 'done'
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                 WHEN 'medium' THEN 2 ELSE 3 END, ticket_id
        """,
        (tech_id,),
        one_record=False,
    ) or []
    prs = db.run_query(
        """
        SELECT pr_id, title, project, author_id, reviewer_id, status, ci_status
        FROM pull_requests WHERE author_id = ? OR reviewer_id = ? ORDER BY pr_id
        """,
        (tech_id, tech_id),
        one_record=False,
    ) or []
    approvals = db.run_query(
        """
        SELECT order_id, part_no, qty FROM parts_orders
        WHERE tech_id = ? AND status = 'pending_approval'
        ORDER BY order_id
        """,
        (tech_id,),
        one_record=False,
    ) or []
    reminders = db.run_query(
        """
        SELECT reminder_id, text, due_at, status FROM reminders
        WHERE tech_id = ? AND status != 'done' ORDER BY due_at
        """,
        (tech_id,),
        one_record=False,
    ) or []
    deploy = db.run_query(
        """SELECT project, environment, deploy_ref, status, deployed_at
        FROM deployments ORDER BY deployed_at DESC LIMIT 1""",
        one_record=True,
    )

    urgent = [
        {"ticket_id": r[0], "summary": r[1], "severity": r[2], "system": r[3], "status": r[4]}
        for r in tickets if r[2] in ("critical", "high")
    ]
    waiting = [
        {"pr_id": r[0], "title": r[1], "project": r[2], "status": r[5], "ci_status": r[6]}
        for r in prs if str(r[4]) == str(tech_id) and r[5] == "awaiting_review"
    ]
    failing = [
        {"pr_id": r[0], "title": r[1], "project": r[2], "ci_status": r[6]}
        for r in prs if str(r[3]) == str(tech_id) and r[6] == "failing"
    ]
    latest = None
    if deploy:
        latest = {"project": deploy[0], "environment": deploy[1], "deploy_ref": deploy[2], "status": deploy[3], "deployed_at": deploy[4]}

    return ToolResult(llm_response={
        "ok": True, "urgent_tickets": urgent, "waiting_reviews": waiting,
        "failing_ci": failing,
        "pending_approvals": [{"order_id": r[0], "part_no": r[1], "qty": r[2]} for r in approvals],
        "reminders": [{"reminder_id": r[0], "text": r[1], "due_at": r[2], "status": r[3]} for r in reminders],
        "latest_deployment": latest, "tech_id": tech_id,
    })
