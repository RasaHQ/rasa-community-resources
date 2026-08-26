"""Local tools for the schedule_inspection skill (auto-discovered)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, customer_id_from_context


@tool(description="Book an inspection appointment for a claim in inspection status.")
async def book_inspection(
    claim_number: str,
    inspection_date: str,
    context: ToolContext = None,
) -> ToolResult:
    """Book an inspection.

    Args:
        claim_number: Claim id to update.
        inspection_date: Preferred date and time for the inspection.
    """
    customer_id = customer_id_from_context(context)
    db = Database()
    normalized = claim_number.strip().upper()
    row = db.run_query(
        """
        SELECT claim_id, claim_status FROM claims
        WHERE customer_id = ? AND upper(claim_id) = ?
        """,
        (customer_id, normalized),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "claim_not_found", "claim_number": normalized}
        )

    claim_id, claim_status = row
    if int(claim_status) != 2:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "inspection_not_available",
                "claim_number": claim_id,
                "claim_status": int(claim_status),
                "hint": "Inspection scheduling is only available when status is 2.",
            }
        )

    db.cursor.execute(
        "UPDATE claims SET inspection_date = ? WHERE claim_id = ? AND customer_id = ?",
        (inspection_date, claim_id, customer_id),
    )
    db.commit()

    if context is not None:
        context.memory.set("inspection_scheduled", True)
        context.memory.set("inspection_date", inspection_date)
        context.memory.set("claim_number", claim_id)

    return ToolResult(
        llm_response={
            "ok": True,
            "claim_number": claim_id,
            "inspection_date": inspection_date,
        }
    )
