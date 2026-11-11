"""Release-note drafting tools."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database


@tool(description="Draft release notes from project pull requests and deployment history.")
async def draft_release_notes(project: str, context: ToolContext = None) -> ToolResult:
    """Gather release evidence without publishing or modifying anything."""
    cleaned = str(project).strip().lower().replace(" ", "-")
    db = Database()
    prs = db.run_query(
        """SELECT pr_id, title, author_id, status, ci_status
        FROM pull_requests WHERE project = ? ORDER BY pr_id""",
        (cleaned,), one_record=False,
    ) or []
    deploy = db.run_query(
        """SELECT deploy_ref, environment, status, deployed_at
        FROM deployments WHERE project = ? ORDER BY deployed_at DESC LIMIT 1""",
        (cleaned,), one_record=True,
    )
    blockers = db.run_query(
        """SELECT ticket_id, summary FROM support_tickets
        WHERE system = ? AND severity = 'critical' AND status != 'done'
        ORDER BY ticket_id""",
        (cleaned,), one_record=False,
    ) or []
    latest = None if not deploy else {"deploy_ref": deploy[0], "environment": deploy[1], "status": deploy[2], "deployed_at": deploy[3]}
    return ToolResult(llm_response={
        "ok": True, "project": cleaned,
        "pull_requests": [{"pr_id": r[0], "title": r[1], "author_id": r[2], "status": r[3], "ci_status": r[4]} for r in prs],
        "latest_deployment": latest,
        "critical_blockers": [{"ticket_id": r[0], "summary": r[1]} for r in blockers],
    })
