"""LOCAL tools for Change Flight — searching and rebooking belong to this skill."""

from __future__ import annotations

from lib.db import (
    PASSENGER_ID,
    TravelDbMissing,
    get_flight_bookings,
    search_flights,
    update_ticket_to_new_flight,
)
from lib.engine import ToolContext, ToolResult, tool


def _brief(booking: dict) -> dict:
    return {
        "flight_id": booking["flight_id"],
        "flight_no": booking["flight_no"],
        "route": f"{booking['departure_airport']}->{booking['arrival_airport']}",
        "departs": str(booking["scheduled_departure"])[:16],
    }


@tool(
    description=(
        "Find alternative flights on the same route as the traveller's current "
        "booking, optionally within a date range."
    )
)
async def search_alternative_flights(context: ToolContext = None) -> ToolResult:
    """Search for other flights on the route of the booking being changed.

    Takes no arguments on purpose. An ordered-block `execute_tool` step stalls
    when the engine cannot fill a parameter, and the model then asks about the
    missing value instead of running the tool. Reading `current_flight_id` from
    memory keeps the step unconditional.
    """
    current_flight_id = context.memory.get("current_flight_id") if context else None
    try:
        bookings = get_flight_bookings()
    except TravelDbMissing as exc:
        return ToolResult(llm_response={"ok": False, "error": "db_missing", "detail": str(exc)})

    if not bookings:
        return ToolResult(llm_response={"ok": False, "error": "no_bookings"})
    if current_flight_id:
        current = next((b for b in bookings if b["flight_id"] == int(current_flight_id)), None)
        if current is None:
            return ToolResult(
                llm_response={"ok": False, "error": "not_a_current_booking",
                              "your_flights": [_brief(b) for b in bookings]}
            )
    elif len(bookings) > 1:
        # Faithful to the original, which stopped here rather than guessing
        # which booking the traveller meant.
        return ToolResult(
            llm_response={"ok": False, "error": "which_flight",
                          "your_flights": [_brief(b) for b in bookings]}
        )
    else:
        current = bookings[0]
    if context is not None:
        context.memory.set("ticket_no", current["ticket_no"])
        context.memory.set("current_flight_id", current["flight_id"])

    results = search_flights(
        departure_airport=current["departure_airport"],
        arrival_airport=current["arrival_airport"],
        # Optional narrowing, read from memory like current_flight_id. The tool
        # takes no arguments so an ordered-block step can call it unconditionally.
        # Optional narrowing, read from memory rather than taken as arguments.
        # Both work; reading memory keeps the conversation one turn shorter,
        # because a bound parameter prompts the model to collect it first.
        start_date=(context.memory.get("search_start_date") if context else None) or None,
        end_date=(context.memory.get("search_end_date") if context else None) or None,
        limit=6,
    )
    # Never offer the flight they already hold.
    results = [r for r in results if r["flight_id"] != current["flight_id"]]

    return ToolResult(
        llm_response={
            "ok": True,
            "current_flight": {
                "flight_no": current["flight_no"],
                "departs": str(current["scheduled_departure"])[:16],
            },
            "count": len(results),
            "options": [
                {
                    "flight_id": r["flight_id"],
                    "flight_no": r["flight_no"],
                    "departs": str(r["scheduled_departure"])[:16],
                }
                for r in results
            ],
        }
    )


@tool(description="Move the traveller's ticket onto the flight they selected.")
async def rebook_flight(context: ToolContext = None) -> ToolResult:
    """Rebook the traveller onto the flight in `selected_flight_id`."""
    flight_id = context.memory.get("selected_flight_id") if context else None
    if not flight_id:
        return ToolResult(llm_response={"ok": False, "error": "no_flight_selected"})
    ticket_no = context.memory.get("ticket_no") if context else None
    old_flight_id = context.memory.get("current_flight_id") if context else None
    if not ticket_no or not old_flight_id:
        return ToolResult(llm_response={"ok": False, "error": "no_ticket_selected"})

    try:
        ok, reason = update_ticket_to_new_flight(
            str(ticket_no), int(old_flight_id), int(flight_id), PASSENGER_ID
        )
    except TravelDbMissing as exc:
        return ToolResult(llm_response={"ok": False, "error": "db_missing", "detail": str(exc)})

    if not ok:
        return ToolResult(llm_response={"ok": False, "error": reason})
    return ToolResult(llm_response={"ok": True, "flight_id": int(flight_id)})
