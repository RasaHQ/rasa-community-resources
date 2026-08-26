"""Flight-status skill tools — local to skills/flight_status/."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import FLIGHT_STATUS_LABELS, Database


@tool(description="Get flight status for a booking reference.")
async def get_flight_status(
    booking_ref: str, context: ToolContext = None
) -> ToolResult:
    """Return flights and status for a booking.

    Args:
        booking_ref: Horizon Travel booking reference such as HT12345.
    """
    cleaned = str(booking_ref).strip().upper().replace(" ", "")
    db = Database()
    rows = db.run_query(
        """
        SELECT flight_number, leg, depart_airport, arrive_airport,
               scheduled_depart, status, gate, delay_minutes
        FROM flights WHERE UPPER(REPLACE(booking_ref, ' ', '')) = ?
        ORDER BY scheduled_depart
        """,
        (cleaned,),
        one_record=False,
    )
    if not rows:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "flights_not_found",
                "booking_ref": cleaned,
            }
        )

    flights = []
    for (
        flight_number,
        leg,
        depart_airport,
        arrive_airport,
        scheduled_depart,
        status,
        gate,
        delay_minutes,
    ) in rows:
        flights.append(
            {
                "flight_number": flight_number,
                "leg": leg,
                "depart_airport": depart_airport,
                "arrive_airport": arrive_airport,
                "scheduled_depart": scheduled_depart,
                "status": status,
                "status_label": FLIGHT_STATUS_LABELS.get(status, status),
                "gate": gate,
                "delay_minutes": int(delay_minutes or 0),
            }
        )

    primary = flights[0]["status"] if flights else "unknown"
    if context is not None:
        context.memory.set("booking_ref", cleaned)
        context.memory.set("flight_status", primary)

    return ToolResult(
        llm_response={
            "ok": True,
            "booking_ref": cleaned,
            "flights": flights,
            "primary_status": primary,
        }
    )
