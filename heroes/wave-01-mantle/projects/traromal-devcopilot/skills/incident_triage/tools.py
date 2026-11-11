"""Read-only incident correlation tools."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database


@tool(description="Correlate open tickets and recent deployments for a service.")
async def triage_incident(project: str, context: ToolContext = None) -> ToolResult:
    """Return evidence for a service incident without changing state."""
    cleaned = str(project).strip().lower().replace(" ", "-")
    db = Database()
    tickets = db.run_query(
        """SELECT ticket_id, summary, severity, status, created_at, updated_at
        FROM support_tickets WHERE system = ? AND status != 'done'
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                 WHEN 'medium' THEN 2 ELSE 3 END, ticket_id""",
        (cleaned,), one_record=False,
    ) or []
    deployments = db.run_query(
        """SELECT deploy_ref, environment, status, deployed_at
        FROM deployments WHERE project = ? ORDER BY deployed_at DESC LIMIT 5""",
        (cleaned,), one_record=False,
    ) or []
    return ToolResult(llm_response={
        "ok": True, "project": cleaned,
        "tickets": [{"ticket_id": r[0], "summary": r[1], "severity": r[2], "status": r[3], "created_at": r[4], "updated_at": r[5]} for r in tickets],
        "deployments": [{"deploy_ref": r[0], "environment": r[1], "status": r[2], "deployed_at": r[3]} for r in deployments],
        "critical_count": sum(1 for r in tickets if r[2] == "critical"),
    })
