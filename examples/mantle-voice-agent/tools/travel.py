"""Shared travel tools — only helpers used by more than one skill.

Skill-owned tools live in skills/<name>/tools.py and are auto-discovered.
"""

from __future__ import annotations

from typing import Optional

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, get_customer, resolve_customer_id
from lib.tool_helpers import active_customer_id, traveler_display_name


@tool(description="Load the demo traveler profile into project memory.")
async def load_customer_profile(
    customer_id: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Ensure customer_id / name fields are available.

    Args:
        customer_id: Optional traveler id. The demo always resolves to Maya
            Chen (456) when omitted or unrecognized.
    """
    # Prefer an explicit arg when the model invents one, otherwise memory /
    # demo default. Unknown ids still fall back to the seeded demo traveler.
    requested = resolve_customer_id(customer_id) if customer_id else active_customer_id(context)
    db = Database()
    row = get_customer(db, requested)
    if not row:
        row = get_customer(db, resolve_customer_id())
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "customer_not_found",
                "customer_id": requested,
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


@tool(description="List the traveler's upcoming bookings and trip summaries.")
async def list_bookings(context: ToolContext = None) -> ToolResult:
    customer_id = active_customer_id(context)
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
    display_name = traveler_display_name(context)
    if not display_name:
        customer = get_customer(db, customer_id)
        if customer:
            display_name = f"{customer[1]} {customer[2]}"

    return ToolResult(
        llm_response={
            "ok": True,
            "bookings": bookings,
            "booking_count": len(bookings),
            "customer_id": customer_id,
            "display_name": display_name,
        }
    )
