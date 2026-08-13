"""Change-booking skill tools — local to skills/change_booking/."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_customer_id


@tool(description="Cancel a booking after the traveler has confirmed.")
async def cancel_booking(
    booking_ref: str, context: ToolContext = None
) -> ToolResult:
    """Cancel a confirmed booking.

    Args:
        booking_ref: Horizon Travel booking reference to cancel.
    """
    customer_id = active_customer_id(context)
    cleaned = str(booking_ref).strip().upper().replace(" ", "")
    db = Database()
    row = db.run_query(
        """
        SELECT booking_ref, trip_name, status FROM bookings
        WHERE customer_id = ? AND UPPER(REPLACE(booking_ref, ' ', '')) = ?
        """,
        (customer_id, cleaned),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "booking_not_found"}
        )

    booking_ref_val, trip_name, status = row
    if status == "cancelled":
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "already_cancelled",
                "booking_ref": booking_ref_val,
            }
        )

    db.connection.execute(
        "UPDATE bookings SET status = ? WHERE booking_ref = ?",
        ("cancelled", booking_ref_val),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("change_confirmed", True)
        context.memory.set("selected_booking_ref", booking_ref_val)

    return ToolResult(
        llm_response={
            "ok": True,
            "booking_ref": booking_ref_val,
            "trip_name": trip_name,
            "status": "cancelled",
        }
    )
