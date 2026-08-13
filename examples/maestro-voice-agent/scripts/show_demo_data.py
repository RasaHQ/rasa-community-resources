#!/usr/bin/env python3
"""Print the demo traveler's bookings — the presenter's cheat sheet.

Usage:
    make show-demo-data
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from lib.database import (  # noqa: E402
    DEMO_AUTH_PIN,
    DEMO_CUSTOMER_ID,
    DEMO_FIRST_NAME,
    DEMO_LAST_NAME,
    FLIGHT_STATUS_LABELS,
    Database,
)

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
MAGENTA = "\033[95m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> None:
    db = Database()
    customer = db.run_query(
        "SELECT first_name, last_name FROM customers WHERE customer_id = ?",
        (DEMO_CUSTOMER_ID,),
    )
    if customer is None:
        print(f"Demo traveler '{DEMO_CUSTOMER_ID}' not found. Run: make reset-db")
        sys.exit(1)

    first_name, last_name = customer
    print(
        f"\n{BOLD}{MAGENTA}Demo traveler: {first_name} {last_name}{RESET}"
        f"  {DIM}(id {DEMO_CUSTOMER_ID}, PIN {DEMO_AUTH_PIN}){RESET}\n"
    )

    print(f"{BLUE}{BOLD}Bookings{RESET}")
    bookings = db.run_query(
        """
        SELECT booking_ref, trip_name, origin, destination, depart_date, status
        FROM bookings WHERE customer_id = ? ORDER BY depart_date
        """,
        (DEMO_CUSTOMER_ID,),
        one_record=False,
    )
    for booking_ref, trip_name, origin, destination, depart_date, status in bookings or []:
        print(
            f"  {GREEN}{booking_ref}{RESET}  {trip_name}  "
            f"{origin} → {destination}  {DIM}{depart_date} ({status}){RESET}"
        )

    print(f"\n{BLUE}{BOLD}Flights{RESET}")
    flights = db.run_query(
        """
        SELECT booking_ref, flight_number, leg, status, delay_minutes, gate
        FROM flights ORDER BY booking_ref, scheduled_depart
        """,
        one_record=False,
    )
    for booking_ref, flight_number, leg, status, delay_minutes, gate in flights or []:
        label = FLIGHT_STATUS_LABELS.get(status, status)
        extra = f", delay {delay_minutes}m" if delay_minutes else ""
        gate_s = f", gate {gate}" if gate else ""
        print(
            f"  {GREEN}{flight_number}{RESET}  {booking_ref} {leg}  "
            f"{label}{extra}{gate_s}"
        )

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    print('  "What trips do I have?"')
    print('  "Is my Lisbon flight on time? Booking H T one two three four five"')
    print('  "I need to cancel a booking"')
    print('  "My bag did not arrive"')
    print('  "How much cabin baggage can I take?"')
    print()


if __name__ == "__main__":
    main()
