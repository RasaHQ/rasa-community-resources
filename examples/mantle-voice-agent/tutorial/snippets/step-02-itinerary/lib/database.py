"""SQLite mock travel backend for the Atlas voice demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_CUSTOMER_ID = "456"
DEMO_FIRST_NAME = "Maya"
DEMO_LAST_NAME = "Chen"
DEMO_USERNAME = "Maya Chen"
DEMO_AUTH_PIN = "4242"

logger = logging.getLogger(__name__)

FLIGHT_STATUS_LABELS = {
    "on_time": "on time",
    "delayed": "delayed",
    "cancelled": "cancelled",
    "boarding": "boarding",
}


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

    table_definitions = {
        "customers": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    auth_pin TEXT NOT NULL
                )
            """,
            "insert_statement": (
                "INSERT INTO customers (customer_id, first_name, last_name, auth_pin) "
                "VALUES (?, ?, ?, ?)"
            ),
        },
        "bookings": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    booking_ref TEXT NOT NULL UNIQUE,
                    trip_name TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    depart_date TEXT NOT NULL,
                    return_date TEXT,
                    hotel_name TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO bookings "
                "(customer_id, booking_ref, trip_name, origin, destination, "
                "depart_date, return_date, hotel_name, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "flights": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS flights (
                    id INTEGER PRIMARY KEY,
                    booking_ref TEXT NOT NULL,
                    flight_number TEXT NOT NULL,
                    leg TEXT NOT NULL,
                    depart_airport TEXT NOT NULL,
                    arrive_airport TEXT NOT NULL,
                    scheduled_depart TEXT NOT NULL,
                    status TEXT NOT NULL,
                    gate TEXT,
                    delay_minutes INTEGER DEFAULT 0,
                    FOREIGN KEY(booking_ref) REFERENCES bookings(booking_ref)
                )
            """,
            "insert_statement": (
                "INSERT INTO flights "
                "(booking_ref, flight_number, leg, depart_airport, arrive_airport, "
                "scheduled_depart, status, gate, delay_minutes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "baggage_reports": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS baggage_reports (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    report_id TEXT NOT NULL UNIQUE,
                    booking_ref TEXT NOT NULL,
                    bag_tag TEXT,
                    last_seen TEXT,
                    description TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO baggage_reports "
                "(customer_id, report_id, booking_ref, bag_tag, last_seen, "
                "description, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = Path(__file__).resolve().parent.parent
        self.database_path = database_path or (
            self.project_root_path / "data" / "travel.db"
        )
        self.source_data_path = self.project_root_path / "data" / "source"

        if self.database_path.exists():
            self.connection = sqlite3.connect(str(self.database_path))
        else:
            self.connection = sqlite3.connect(":memory:")
            self.create_schema()
            self.load_data()
            self.save_to_disk()

        self.cursor = self.connection.cursor()

    def create_schema(self) -> None:
        for definition in self.table_definitions.values():
            self.connection.execute(definition["create_statement"])
        self.connection.commit()

    def load_data(self) -> None:
        for source_file in sorted(self.source_data_path.glob("*.json")):
            with open(source_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            table_name = source_file.stem.lower()
            if table_name in self.table_definitions:
                self.insert_data(table_name, data)

    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> None:
        insert_statement = self.table_definitions[table_name]["insert_statement"]
        for row in data:
            self.connection.execute(insert_statement, tuple(row.values()))
        self.connection.commit()

    def save_to_disk(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.database_path)) as backup_db:
            self.connection.backup(backup_db)

    def run_query(
        self, query: str, parameters: Tuple = (), one_record: bool = True
    ) -> Union[Tuple, List[Tuple], None]:
        self.cursor.execute(query, parameters)
        if one_record:
            return self.cursor.fetchone()
        return self.cursor.fetchall()

    def commit(self) -> None:
        self.connection.commit()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.connection.close()


def resolve_customer_id(context_customer_id: Optional[str] = None) -> str:
    """Return the active demo traveler id (defaults to Maya / 456)."""
    if context_customer_id and str(context_customer_id).strip():
        return str(context_customer_id).strip()
    return DEMO_CUSTOMER_ID


def get_customer(
    db: Database, customer_id: str
) -> Optional[Tuple[str, str, str, str]]:
    row = db.run_query(
        "SELECT customer_id, first_name, last_name, auth_pin "
        "FROM customers WHERE customer_id = ?",
        (customer_id,),
        one_record=True,
    )
    return row  # type: ignore[return-value]


def next_baggage_report_id(db: Database) -> str:
    row = db.run_query(
        "SELECT COUNT(*) FROM baggage_reports",
        one_record=True,
    )
    count = int(row[0]) if row else 0
    return f"BAG{1000 + count + 1}"
