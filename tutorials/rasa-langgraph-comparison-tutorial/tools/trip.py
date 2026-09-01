"""GLOBAL tools — shared by more than one skill, imported explicitly.

`list_flight_bookings` is global because three skills need it: Change Flight
starts from it, and the hotel and car skills use the arrival city to work out
where the traveller is going. It is skill-agnostic and about the traveller
rather than any one workflow, so it lives at the project root.

In the CALM v1 original this was `action: list_flight_bookings` repeated in
several flows, writing shared slots. The dependency is now declared in each
skill's `import_tools`, which is what makes a skill folder portable.
"""

from __future__ import annotations

from lib.db import TravelDbMissing, get_flight_bookings
from lib.engine import ToolContext, ToolResult, tool


def _summarise(booking: dict) -> dict:
    return {
        "ticket_no": booking["ticket_no"],
        "flight_id": booking["flight_id"],
        "flight_no": booking["flight_no"],
        "from": booking["departure_airport"],
        "to": booking["arrival_airport"],
        "departs": str(booking["scheduled_departure"])[:16],
        "status": booking["status"],
    }


@tool(
    description=(
        "List the flights the traveller currently has booked. Call this before "
        "changing a flight, and to find out which city they are travelling to."
    )
)
async def list_flight_bookings(context: ToolContext = None) -> ToolResult:
    """Read the traveller's current flight bookings."""
    try:
        bookings = get_flight_bookings()
    except TravelDbMissing as exc:
        return ToolResult(llm_response={"ok": False, "error": "db_missing", "detail": str(exc)})

    if not bookings:
        return ToolResult(llm_response={"ok": True, "count": 0, "bookings": []})

    # The destination is a fact about the trip, so it belongs in project memory
    # where the hotel, car and excursion skills can read it without asking.
    if context is not None:
        context.memory.set("trip_destination_code", bookings[0]["arrival_airport"])

    return ToolResult(
        llm_response={
            "ok": True,
            "count": len(bookings),
            # Exactly one booking is the case the change-flight skill can act on
            # without asking which; the original tracked this as `unique_booking`.
            "unique": len(bookings) == 1,
            "bookings": [_summarise(b) for b in bookings],
        }
    )
