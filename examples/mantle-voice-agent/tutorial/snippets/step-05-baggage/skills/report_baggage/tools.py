"""Report-baggage skill tools — local to skills/report_baggage/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, next_baggage_report_id
from lib.tool_helpers import active_customer_id


@tool(description="Submit a lost-baggage report for the traveler.")
async def submit_baggage_report(
    booking_ref: str,
    bag_tag: str,
    last_seen: str,
    description: str,
    context: ToolContext = None,
) -> ToolResult:
    """Create a baggage report.

    Args:
        booking_ref: Booking associated with the missing bag.
        bag_tag: Bag tag number if known.
        last_seen: Where the bag was last seen.
        description: Short description of the bag.
    """
    customer_id = active_customer_id(context)
    cleaned_ref = str(booking_ref).strip().upper().replace(" ", "")
    db = Database()
    report_id = next_baggage_report_id(db)
    db.connection.execute(
        """
        INSERT INTO baggage_reports
        (customer_id, report_id, booking_ref, bag_tag, last_seen, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            report_id,
            cleaned_ref,
            str(bag_tag).strip(),
            str(last_seen).strip(),
            str(description).strip(),
            "open",
        ),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("details_verified", True)
        context.memory.set("submitted_report_id", report_id)

    spoken = " ".join(list(report_id))

    return ToolResult(
        llm_response={
            "ok": True,
            "report_id": report_id,
            "report_id_spoken": spoken,
            "booking_ref": cleaned_ref,
            "status": "open",
        }
    )
