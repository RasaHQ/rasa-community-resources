"""Shared travel tools — new Skills API (`rasa_sdk`) with calm_v2 fallback."""

from __future__ import annotations

from typing import Optional

try:
    from rasa_sdk import ToolContext, ToolResult, tool
except ImportError:  # pragma: no cover - pre-Skills package path
    from rasa.calm_v2.tools.decorator import ToolContext, tool
    from rasa.calm_v2.tools.result import ToolResult

from lib.database import (
    DEMO_AUTH_PIN,
    FLIGHT_STATUS_LABELS,
    Database,
    get_customer,
    next_baggage_report_id,
    resolve_customer_id,
)


def _customer_id(context: Optional[ToolContext]) -> str:
    if context is None:
        return resolve_customer_id()
    return resolve_customer_id(context.memory.get("customer_id"))


@tool(description="Load the demo traveler profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure customer_id / name fields are available."""
    customer_id = _customer_id(context)
    db = Database()
    row = get_customer(db, customer_id)
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "customer_not_found",
                "customer_id": customer_id,
            }
        )

    cid, first_name, last_name, _pin = row
    if context is not None:
        context.memory.set("customer_id", cid)
        context.memory.set("customer_first_name", first_name)
        context.memory.set("customer_last_name", last_name)

    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": cid,
            "customer_first_name": first_name,
            "customer_last_name": last_name,
            "display_name": f"{first_name} {last_name}",
        }
    )


@tool(description="Verify the traveler's voice PIN and mark them authenticated.")
async def verify_traveler_pin(pin: str, context: ToolContext = None) -> ToolResult:
    """Verify the traveler PIN.

    Args:
        pin: Four-digit PIN spoken or typed by the traveler.
    """
    customer_id = _customer_id(context)
    db = Database()
    row = get_customer(db, customer_id)
    if not row:
        return ToolResult(
            llm_response={"ok": False, "error": "customer_not_found"}
        )

    _cid, first_name, last_name, auth_pin = row
    cleaned = "".join(ch for ch in str(pin) if ch.isdigit())
    success = cleaned == str(auth_pin)
    if context is not None and success:
        context.memory.set("authenticated", True)

    return ToolResult(
        llm_response={
            "ok": success,
            "authenticated": success,
            "display_name": f"{first_name} {last_name}",
            "hint": (
                "PIN accepted."
                if success
                else f"PIN rejected. Demo PIN is {DEMO_AUTH_PIN}."
            ),
        }
    )


@tool(description="List the traveler's upcoming bookings and trip summaries.")
async def list_bookings(context: ToolContext = None) -> ToolResult:
    customer_id = _customer_id(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT booking_ref, trip_name, origin, destination, depart_date,
               return_date, hotel_name, status
        FROM bookings WHERE customer_id = ?
        ORDER BY depart_date
        """,
        (customer_id,),
        one_record=False,
    )
    bookings = [
        {
            "booking_ref": booking_ref,
            "trip_name": trip_name,
            "origin": origin,
            "destination": destination,
            "depart_date": depart_date,
            "return_date": return_date,
            "hotel_name": hotel_name,
            "status": status,
        }
        for (
            booking_ref,
            trip_name,
            origin,
            destination,
            depart_date,
            return_date,
            hotel_name,
            status,
        ) in rows
        or []
    ]
    return ToolResult(
        llm_response={
            "ok": True,
            "bookings": bookings,
            "booking_count": len(bookings),
            "customer_id": customer_id,
        }
    )


@tool(description="Look up a single booking by booking reference.")
async def get_booking(booking_ref: str, context: ToolContext = None) -> ToolResult:
    """Look up a booking.

    Args:
        booking_ref: Horizon Travel booking reference such as HT12345.
    """
    customer_id = _customer_id(context)
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


@tool(description="Cancel a booking after the traveler has confirmed.")
async def cancel_booking(
    booking_ref: str, context: ToolContext = None
) -> ToolResult:
    """Cancel a confirmed booking.

    Args:
        booking_ref: Horizon Travel booking reference to cancel.
    """
    customer_id = _customer_id(context)
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
    customer_id = _customer_id(context)
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
