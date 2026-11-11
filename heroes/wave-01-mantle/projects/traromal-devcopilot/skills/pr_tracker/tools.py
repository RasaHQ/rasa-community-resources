"""PR-tracker skill tools â€” local to skills/pr_tracker/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id


@tool(description="List pull requests waiting on the developer or opened by them.")
async def list_pull_requests(context: ToolContext = None) -> ToolResult:
    """Return PRs where the developer is reviewer or author."""
    tech_id = active_tech_id(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT pr_id, title, project, author_id, reviewer_id, status, ci_status
        FROM pull_requests
        WHERE author_id = ? OR reviewer_id = ?
        ORDER BY pr_id
        """,
        (tech_id, tech_id),
        one_record=False,
    )
    waiting_on_me = []
    mine = []
    for (
        pr_id,
        title,
        project,
        author_id,
        reviewer_id,
        status,
        ci_status,
    ) in rows or []:
        entry = {
            "pr_id": pr_id,
            "title": title,
            "project": project,
            "status": status,
            "ci_status": ci_status,
        }
        if str(reviewer_id) == str(tech_id) and status == "awaiting_review":
            waiting_on_me.append(entry)
        if str(author_id) == str(tech_id):
            entry["ci_failing"] = ci_status == "failing"
            mine.append(entry)

    return ToolResult(
        llm_response={
            "ok": True,
            "waiting_on_me": waiting_on_me,
            "waiting_on_me_count": len(waiting_on_me),
            "my_prs": mine,
            "my_pr_count": len(mine),
            "tech_id": tech_id,
        }
    )
