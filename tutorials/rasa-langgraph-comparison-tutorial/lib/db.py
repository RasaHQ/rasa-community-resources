"""Travel database access, ported from the CALM v1 implementation.

The SQL is the original's. What changed is the shape around it: these are plain
functions returning plain data, with no Rasa SDK types, no tracker and no slot
names. The Mantle tools in ``tools/`` and ``skills/*/tools.py`` are thin wrappers
that add memory writes — which keeps the data layer testable on its own, and is
why ``make db-check`` can exercise it without an agent.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent.parent


def _resolve_db() -> Path:
    """Where travel.sqlite lives.

    Mantle packages the project into a temp snapshot and runs tools from there,
    so a path derived from ``__file__`` points inside that snapshot — where a
    gitignored database does not exist. The symptom is a tool reporting
    "database not built" while the file is plainly sitting in the project.

    Resolution order:
      1. ``TRAVEL_DB``, for anyone who wants it somewhere specific
      2. the working directory, which is the project when you run rasa from it
      3. next to this module, which is right for scripts and tests
    """
    override = os.environ.get("TRAVEL_DB")
    if override:
        return Path(override)
    cwd_db = Path.cwd() / "travel.sqlite"
    if cwd_db.exists():
        return cwd_db
    return MODULE_ROOT / "travel.sqlite"


def _seed_file() -> Path | None:
    """The fixture, wherever it can be found — snapshot included."""
    for candidate in (MODULE_ROOT / "data" / "travel_seed.sql", Path.cwd() / "data" / "travel_seed.sql"):
        if candidate.exists():
            return candidate
    return None


DB_FILE = _resolve_db()

# The signed-in traveller. LangGraph's tutorial hard-codes the same passenger;
# a real deployment resolves this from the authenticated session.
PASSENGER_ID = "3442 587242"


class TravelDbMissing(RuntimeError):
    """The fixture has not been built yet."""


def _connect() -> sqlite3.Connection:
    db = _resolve_db()
    if not db.exists():
        # Build it rather than failing. The fixture is 50 KB and rebuilds in
        # well under a second, so there is no reason to make a missing database
        # someone's problem — least of all mid-conversation.
        seed = _seed_file()
        if seed is None:
            raise TravelDbMissing(
                f"{db} does not exist and no fixture was found. Run: make db"
            )
        db.parent.mkdir(parents=True, exist_ok=True)
        builder = sqlite3.connect(db)
        builder.executescript(seed.read_text(encoding="utf-8"))
        builder.commit()
        builder.close()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with _connect() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# ---------------------------------------------------------------------------
# Flights
# ---------------------------------------------------------------------------


def get_flight_bookings(passenger_id: str = PASSENGER_ID) -> list[dict]:
    """Every flight the passenger currently holds, earliest first."""
    return _rows(
        """
        SELECT t.ticket_no, t.book_ref, f.flight_id, f.flight_no,
               f.departure_airport, f.arrival_airport,
               f.scheduled_departure, f.scheduled_arrival, f.status,
               tf.fare_conditions, tf.amount
        FROM tickets t
        JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
        JOIN flights f ON f.flight_id = tf.flight_id
        WHERE t.passenger_id = ?
        ORDER BY f.scheduled_departure
        """,
        (passenger_id,),
    )


def search_flights(
    departure_airport: str | None = None,
    arrival_airport: str | None = None,
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Flights matching a route and an optional departure window."""
    query = "SELECT * FROM flights WHERE 1 = 1"
    params: list[Any] = []
    if departure_airport:
        query += " AND departure_airport = ?"
        params.append(departure_airport)
    if arrival_airport:
        query += " AND arrival_airport = ?"
        params.append(arrival_airport)
    if start_date:
        query += " AND scheduled_departure >= ?"
        params.append(str(start_date))
    if end_date:
        query += " AND scheduled_departure <= ?"
        params.append(str(end_date))
    query += " ORDER BY scheduled_departure LIMIT ?"
    params.append(limit)
    return _rows(query, tuple(params))


def update_ticket_to_new_flight(
    ticket_no: str,
    old_flight_id: int,
    new_flight_id: int,
    passenger_id: str = PASSENGER_ID,
) -> tuple[bool, str]:
    """Move a ticket onto another flight.

    ``old_flight_id`` identifies which leg to move: one ticket can cover several
    flights, so the ticket number alone does not.

    Returns ``(ok, reason)``. Every refusal is a named reason rather than a
    raised exception, so the tool layer can hand the model a fact to act on
    instead of a stack trace.
    """
    with _connect() as conn:
        new_flight = conn.execute(
            "SELECT * FROM flights WHERE flight_id = ?", (new_flight_id,)
        ).fetchone()
        if new_flight is None:
            return False, "flight_not_found"

        owned = conn.execute(
            "SELECT 1 FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
            (ticket_no, passenger_id),
        ).fetchone()
        if owned is None:
            return False, "not_your_ticket"

        booked = conn.execute(
            "SELECT 1 FROM ticket_flights WHERE ticket_no = ? AND flight_id = ?",
            (ticket_no, old_flight_id),
        ).fetchone()
        if booked is None:
            return False, "ticket_not_booked"

        # Key on the leg, not just the ticket. One ticket covers an outbound and
        # a return, both under the same ticket_no — updating by ticket_no alone
        # silently moves both legs onto the new flight.
        conn.execute(
            "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ? AND flight_id = ?",
            (new_flight_id, ticket_no, old_flight_id),
        )
        conn.commit()
    return True, "ok"


# ---------------------------------------------------------------------------
# Cars, hotels, excursions
# ---------------------------------------------------------------------------


def hotel_locations() -> set[str]:
    return {r["location"] for r in _rows("SELECT DISTINCT location FROM hotels")}


def search_hotels(location: str | None = None, price_tier: str | None = None) -> list[dict]:
    query = "SELECT * FROM hotels WHERE 1 = 1"
    params: list[Any] = []
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if price_tier:
        query += " AND price_tier LIKE ?"
        params.append(f"%{price_tier}%")
    return _rows(query, tuple(params))


def search_car_rentals(location: str | None = None, price_tier: str | None = None) -> list[dict]:
    query = "SELECT * FROM car_rentals WHERE 1 = 1"
    params: list[Any] = []
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if price_tier:
        query += " AND price_tier LIKE ?"
        params.append(f"%{price_tier}%")
    return _rows(query, tuple(params))


def search_excursions(location: str | None = None, keywords: str | None = None) -> list[dict]:
    query = "SELECT * FROM trip_recommendations WHERE 1 = 1"
    params: list[Any] = []
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if keywords:
        query += " AND keywords LIKE ?"
        params.append(f"%{keywords}%")
    return _rows(query, tuple(params))


def book(table: str, record_id: int) -> tuple[bool, str]:
    """Mark a car rental, hotel or excursion as booked."""
    if table not in {"car_rentals", "hotels", "trip_recommendations"}:
        return False, "unknown_inventory"
    with _connect() as conn:
        row = conn.execute(f"SELECT booked FROM {table} WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            return False, "not_found"
        if row["booked"]:
            return False, "already_booked"
        conn.execute(f"UPDATE {table} SET booked = 1 WHERE id = ?", (record_id,))
        conn.commit()
    return True, "ok"
