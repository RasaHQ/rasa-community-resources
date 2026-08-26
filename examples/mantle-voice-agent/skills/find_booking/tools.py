"""Find-booking skill tools — local to skills/find_booking/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database
from lib.tool_helpers import active_customer_id


@tool(description="Look up a single booking by booking reference.")
async def get_booking(booking_ref: str, context: ToolContext = None) -> ToolResult:
    """Look up a booking.

    Args:
        booking_ref: Horizon Travel booking reference such as HT12345.
    """
    customer_id = active_customer_id(context)
    cleaned = str(booking_ref).strip().upper().replace(" ", "")
    db = Database()
    row = db.run_query(
        """
        SELECT booking_ref, trip_name, origin, destination, depart_date,
               return_date, hotel_name, status
        FROM bookings
        WHERE customer_id = ? AND UPPER(REPLACE(booking_ref, ' ', '')) = ?
        """,
        (customer_id, cleaned),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "booking_not_found",
                "booking_ref": cleaned,
            }
        )

    (
        booking_ref_val,
        trip_name,
        origin,
        destination,
        depart_date,
        return_date,
        hotel_name,
        status,
    ) = row

    if context is not None:
        context.memory.set("selected_booking_ref", booking_ref_val)
        context.memory.set("selected_trip_name", trip_name)

    return ToolResult(
        llm_response={
            "ok": True,
            "booking": {
                "booking_ref": booking_ref_val,
                "trip_name": trip_name,
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date,
                "return_date": return_date,
                "hotel_name": hotel_name,
                "status": status,
            },
        }
    )
