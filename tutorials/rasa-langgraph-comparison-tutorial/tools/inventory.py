"""GLOBAL tools — searching and booking the destination inventory.

Hotels, cars and excursions are three skills doing the same two things against
three tables, so the search and the booking live here once and each skill
imports what it needs. In the CALM v1 original these were six near-identical
custom actions.
"""

from __future__ import annotations

from lib.db import (
    TravelDbMissing,
    book,
    hotel_locations,
    search_car_rentals,
    search_excursions,
    search_hotels,
)
from lib.engine import ToolContext, ToolResult, tool


def _fail(exc: TravelDbMissing) -> ToolResult:
    return ToolResult(llm_response={"ok": False, "error": "db_missing", "detail": str(exc)})


@tool(
    description=(
        "Check whether we have anything at all in a city before asking the "
        "traveller for dates or preferences."
    )
)
async def check_destination(city: str, context: ToolContext = None) -> ToolResult:
    """Is this a city we cover?

    Args:
        city: The city the traveller named, e.g. Basel.
    """
    try:
        known = hotel_locations()
    except TravelDbMissing as exc:
        return _fail(exc)

    match = next((c for c in known if c.lower() == city.strip().lower()), None)
    if match is None:
        return ToolResult(
            llm_response={"ok": False, "error": "city_not_covered", "known_cities": sorted(known)}
        )
    if context is not None:
        context.memory.set("trip_destination", match)
    return ToolResult(llm_response={"ok": True, "city": match})


@tool(description="Search hotels in a city, optionally filtered by price tier.")
async def find_hotels(
    city: str, price_tier: str = "", context: ToolContext = None
) -> ToolResult:
    """Search hotels.

    Args:
        city: City to search in.
        price_tier: Optional tier, e.g. Luxury, Upscale, Midscale, Upper Midscale.
    """
    try:
        rows = search_hotels(city, price_tier or None)
    except TravelDbMissing as exc:
        return _fail(exc)
    return ToolResult(
        llm_response={
            "ok": True,
            "count": len(rows),
            "options": [
                {"id": r["id"], "name": r["name"], "price_tier": r["price_tier"], "booked": bool(r["booked"])}
                for r in rows
            ],
        }
    )


@tool(description="Search rental cars in a city, optionally filtered by price tier.")
async def find_cars(city: str, price_tier: str = "", context: ToolContext = None) -> ToolResult:
    """Search rental cars.

    Args:
        city: City to search in.
        price_tier: Optional tier, e.g. Economy, Midsize, Luxury.
    """
    try:
        rows = search_car_rentals(city, price_tier or None)
    except TravelDbMissing as exc:
        return _fail(exc)
    return ToolResult(
        llm_response={
            "ok": True,
            "count": len(rows),
            "options": [
                {"id": r["id"], "name": r["name"], "price_tier": r["price_tier"], "booked": bool(r["booked"])}
                for r in rows
            ],
        }
    )


@tool(description="Search things to do in a city, optionally by keyword.")
async def find_excursions(
    city: str, keywords: str = "", context: ToolContext = None
) -> ToolResult:
    """Search excursions.

    Args:
        city: City to search in.
        keywords: Optional interest, e.g. museum, art, history.
    """
    try:
        rows = search_excursions(city, keywords or None)
    except TravelDbMissing as exc:
        return _fail(exc)
    return ToolResult(
        llm_response={
            "ok": True,
            "count": len(rows),
            "options": [
                {"id": r["id"], "name": r["name"], "details": r["details"][:110], "booked": bool(r["booked"])}
                for r in rows
            ],
        }
    )


@tool(description="Book a hotel, rental car or excursion the traveller has chosen.")
async def book_item(kind: str, item_id: int, context: ToolContext = None) -> ToolResult:
    """Book one item from a previous search.

    Args:
        kind: One of hotel, car, excursion.
        item_id: The id of the chosen option, from the search results.
    """
    table = {"hotel": "hotels", "car": "car_rentals", "excursion": "trip_recommendations"}.get(
        kind.strip().lower()
    )
    if table is None:
        return ToolResult(llm_response={"ok": False, "error": "unknown_kind", "kind": kind})

    try:
        ok, reason = book(table, int(item_id))
    except TravelDbMissing as exc:
        return _fail(exc)
    if not ok:
        return ToolResult(llm_response={"ok": False, "error": reason})
    return ToolResult(llm_response={"ok": True, "kind": kind, "item_id": int(item_id)})
