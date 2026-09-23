"""Deploy-gate skill tools â€” local to skills/deploy_gate/."""

from __future__ import annotations

from datetime import datetime, timezone

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id

_ENVIRONMENTS = {"staging", "production"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _next_deploy_ref(db: Database) -> str:
    row = db.run_query(
        "SELECT deploy_ref FROM deployments ORDER BY id DESC LIMIT 1",
        one_record=True,
    )
    if not row:
        return "DEP301"
    try:
        number = int(str(row[0])[3:]) + 1
    except ValueError:
        number = 301
    return f"DEP{number}"


@tool(description="Check whether a project is safe to deploy right now.")
async def check_deploy_blockers(
    project: str, context: ToolContext = None
) -> ToolResult:
    """Look for critical open tickets on the project.

    Args:
        project: Project or service name to deploy, such as auth-service.
    """
    cleaned = str(project).strip().lower().replace(" ", "-")
    tech_id = active_tech_id(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT ticket_id, summary FROM support_tickets
        WHERE system = ? AND severity = 'critical' AND status != 'done'
        """,
        (cleaned,),
        one_record=False,
    )
    blockers = [
        {"ticket_id": tid, "summary": summary} for (tid, summary) in rows or []
    ]
    blocked = len(blockers) > 0

    if context is not None:
        context.memory.set("project_name", cleaned)
        context.memory.set("blockers_checked", True)
        context.memory.set("blocked", blocked)

    return ToolResult(
        llm_response={
            "ok": True,
            "project": cleaned,
            "blocked": blocked,
            "blockers": blockers,
            "blocker_count": len(blockers),
        }
    )


@tool(description="Record a confirmed deployment of a project.")
async def record_deployment(
    environment: str, context: ToolContext = None
) -> ToolResult:
    """Log the deployment after the developer confirmed.

    Args:
        environment: Target environment, staging or production.
    """
    env = str(environment).strip().lower()
    if env not in _ENVIRONMENTS:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_environment",
                "allowed": sorted(_ENVIRONMENTS),
            }
        )

    project = None
    if context is not None:
        project = context.memory.get("project_name")
    if not project:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "project_not_checked",
                "hint": "Run check_deploy_blockers before recording a deploy.",
            }
        )

    # Re-check at record time so nothing slipped in after the gate.
    db = Database()
    rows = db.run_query(
        """
        SELECT ticket_id FROM support_tickets
        WHERE system = ? AND severity = 'critical' AND status != 'done'
        """,
        (str(project),),
        one_record=False,
    )
    if rows:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "deploy_blocked",
                "project": project,
                "blockers": [r[0] for r in rows],
                "hint": "Critical tickets are open on this project.",
            }
        )

    tech_id = active_tech_id(context)
    deploy_ref = _next_deploy_ref(db)
    db.connection.execute(
        """
        INSERT INTO deployments
        (tech_id, project, environment, deploy_ref, status, deployed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tech_id, project, env, deploy_ref, "success", _now()),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("deploy_ref", deploy_ref)

    return ToolResult(
        llm_response={
            "ok": True,
            "deploy_ref": deploy_ref,
            "deploy_ref_spoken": " ".join(list(deploy_ref)),
            "project": project,
            "environment": env,
            "status": "success",
        }
    )
