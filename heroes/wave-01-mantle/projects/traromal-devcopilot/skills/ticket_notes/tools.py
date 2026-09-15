"""Ticket-notes skill tools â€” local to skills/ticket_notes/."""

from __future__ import annotations

from datetime import datetime, timezone

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_tech_id

_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}
_ALLOWED_STATUSES = {"open", "in_progress", "done"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def _next_ticket_id(db: Database) -> str:
    """Next demo ticket id after the highest one on file."""
    row = db.run_query(
        "SELECT ticket_id FROM support_tickets ORDER BY id DESC LIMIT 1",
        one_record=True,
    )
    if not row:
        return "TKT1001"
    try:
        number = int(str(row[0])[3:]) + 1
    except ValueError:
        number = 1001
    return f"TKT{number}"


def _tickets_for(db: Database, tech_id: str) -> list[dict[str, str]]:
    rows = db.run_query(
        """
        SELECT ticket_id, summary, severity, system, status, created_at
        FROM support_tickets
        WHERE tech_id = ?
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                 WHEN 'medium' THEN 2 ELSE 3 END,
                 CASE status WHEN 'in_progress' THEN 0 WHEN 'open' THEN 1
                 ELSE 2 END,
                 created_at
        """,
        (tech_id,),
        one_record=False,
    )
    return [
        {
            "ticket_id": ticket_id,
            "summary": summary,
            "severity": severity,
            "system": system,
            "status": status,
            "created_at": created_at,
        }
        for (ticket_id, summary, severity, system, status, created_at) in rows
        or []
    ]


@tool(description="List all support tickets assigned to the developer.")
async def list_assigned_tickets(context: ToolContext = None) -> ToolResult:
    """Return the active developer's tickets with status and severity."""
    tech_id = active_tech_id(context)
    db = Database()
    tickets = _tickets_for(db, tech_id)
    open_count = sum(1 for t in tickets if t["status"] != "done")
    return ToolResult(
        llm_response={
            "ok": True,
            "tickets": tickets,
            "ticket_count": len(tickets),
            "open_count": open_count,
            "tech_id": tech_id,
        }
    )


@tool(description="Update the status of an assigned ticket.")
async def update_ticket_status(
    new_status: str, context: ToolContext = None
) -> ToolResult:
    """Move a ticket to in_progress or done.

    Args:
        new_status: The target status, either in_progress or done.
    """
    ticket_id = None
    if context is not None:
        ticket_id = context.memory.get("selected_ticket_id")
    if not ticket_id:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_ticket_selected",
                "hint": "Ask which ticket to update before calling this tool.",
            }
        )

    status = str(new_status).strip().lower().replace(" ", "_")
    if status not in _ALLOWED_STATUSES:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_status",
                "status": status,
                "allowed": sorted(_ALLOWED_STATUSES),
            }
        )

    tech_id = active_tech_id(context)
    db = Database()
    row = db.run_query(
        "SELECT ticket_id FROM support_tickets "
        "WHERE ticket_id = ? AND tech_id = ?",
        (ticket_id, tech_id),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "ticket_not_found",
                "ticket_id": ticket_id,
            }
        )

    db.connection.execute(
        "UPDATE support_tickets SET status = ?, updated_at = ? "
        "WHERE ticket_id = ?",
        (status, _now(), ticket_id),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("ticket_ref", ticket_id)

    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "ticket_id_spoken": " ".join(list(ticket_id)),
            "status": status,
        }
    )


@tool(description="Give a daily briefing of the developer's support tickets.")
async def get_daily_briefing(context: ToolContext = None) -> ToolResult:
    """Summarize open work: counts by status and at-risk tickets."""
    tech_id = active_tech_id(context)
    db = Database()
    tickets = _tickets_for(db, tech_id)

    by_status = {status: 0 for status in _ALLOWED_STATUSES}
    at_risk = []
    for ticket in tickets:
        by_status[ticket["status"]] = by_status.get(ticket["status"], 0) + 1
        if (
            ticket["status"] != "done"
            and _SEVERITY_ORDER.get(ticket["severity"], 9) <= 1
        ):
            at_risk.append(ticket)

    return ToolResult(
        llm_response={
            "ok": True,
            "total": len(tickets),
            "open": by_status.get("open", 0),
            "in_progress": by_status.get("in_progress", 0),
            "done": by_status.get("done", 0),
            "at_risk": at_risk,
            "at_risk_count": len(at_risk),
            "tech_id": tech_id,
        }
    )


@tool(description="Give a standup: recently finished work, current work, and blockers.")
async def get_standup(context: ToolContext = None) -> ToolResult:
    """Summarize wrapped-up work, in-progress work, and blockers."""
    tech_id = active_tech_id(context)
    db = Database()
    tickets = _tickets_for(db, tech_id)

    done = [t for t in tickets if t["status"] == "done"]
    in_progress = [t for t in tickets if t["status"] == "in_progress"]
    blockers = [
        t
        for t in tickets
        if t["status"] != "done"
        and _SEVERITY_ORDER.get(t["severity"], 9) <= 1
    ]

    return ToolResult(
        llm_response={
            "ok": True,
            "finished": done,
            "finished_count": len(done),
            "in_progress": in_progress,
            "in_progress_count": len(in_progress),
            "blockers": blockers,
            "blocker_count": len(blockers),
            "tech_id": tech_id,
        }
    )


@tool(description="Add a spoken note to an assigned support ticket.")
async def add_ticket_comment(
    comment: str, context: ToolContext = None
) -> ToolResult:
    """Append a note to a ticket selected in skill memory.

    Args:
        comment: The note text confirmed by the developer.
    """
    ticket_id = None
    if context is not None:
        ticket_id = context.memory.get("selected_ticket_id")
    if not ticket_id:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_ticket_selected",
                "hint": "Ask which ticket to annotate before calling this tool.",
            }
        )

    tech_id = active_tech_id(context)
    db = Database()
    row = db.run_query(
        "SELECT ticket_id FROM support_tickets "
        "WHERE ticket_id = ? AND tech_id = ?",
        (ticket_id, tech_id),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "ticket_not_found",
                "ticket_id": ticket_id,
            }
        )

    db.connection.execute(
        "INSERT INTO ticket_comments (ticket_id, tech_id, comment, created_at) "
        "VALUES (?, ?, ?, ?)",
        (ticket_id, tech_id, str(comment).strip(), _now()),
    )
    db.connection.execute(
        "UPDATE support_tickets SET updated_at = ? WHERE ticket_id = ?",
        (_now(), ticket_id),
    )
    db.commit()
    db.save_to_disk()

    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "comment": str(comment).strip(),
        }
    )


@tool(description="File a cleaned-up support ticket from incident notes.")
async def file_support_ticket(
    summary: str,
    severity: str,
    system: str,
    repro_steps: str = "none",
    context: ToolContext = None,
) -> ToolResult:
    """Create a support ticket in the demo operations database.

    Args:
        summary: One-sentence technical summary confirmed by the developer.
        severity: One of critical, high, medium, low.
        system: Affected system or service, for example auth-service.
        repro_steps: Steps to reproduce, or none.
    """
    tech_id = active_tech_id(context)
    db = Database()
    ticket_id = _next_ticket_id(db)
    db.connection.execute(
        """
        INSERT INTO support_tickets
        (tech_id, ticket_id, summary, severity, system, repro_steps, status,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tech_id,
            ticket_id,
            summary,
            severity.lower(),
            system,
            repro_steps,
            "open",
            _now(),
            _now(),
        ),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("ticket_ref", ticket_id)

    spoken = " ".join(list(ticket_id))
    return ToolResult(
        llm_response={
            "ok": True,
            "ticket_id": ticket_id,
            "ticket_id_spoken": spoken,
            "summary": summary,
            "severity": severity.lower(),
            "system": system,
            "status": "open",
        }
    )
