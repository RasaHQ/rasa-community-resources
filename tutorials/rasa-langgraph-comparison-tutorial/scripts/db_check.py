#!/usr/bin/env python3
"""Query the travel database directly, without the agent in the way.

When something looks wrong, this answers "is it the data or is it the agent?"
in one command.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from lib.db import (  # noqa: E402
    PASSENGER_ID,
    TravelDbMissing,
    _resolve_db,
    get_flight_bookings,
    search_car_rentals,
    search_excursions,
    search_hotels,
)


def main() -> int:
    print(f"\n  database : {_resolve_db()}")
    print(f"  passenger: {PASSENGER_ID}\n")
    try:
        bookings = get_flight_bookings()
    except TravelDbMissing as exc:
        print(f"  ✗ {exc}\n")
        return 1

    print("  flights booked")
    for b in bookings:
        print(f"    {b['flight_no']}  {b['departure_airport']}->{b['arrival_airport']}"
              f"  {str(b['scheduled_departure'])[:16]}  {b['status']}")

    city = bookings[0]["arrival_airport"] if bookings else ""
    for label, rows in (
        ("hotels in Basel", search_hotels("Basel")),
        ("cars in Basel", search_car_rentals("Basel")),
        ("excursions in Basel", search_excursions("Basel")),
    ):
        print(f"\n  {label}: {len(rows)}")
        for r in rows[:3]:
            mark = " (booked)" if r["booked"] else ""
            print(f"    {r['name']}{mark}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
