"""SQLite mock dealership backend for the Autono voice demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_USERNAME = "Alex Rivera"

logger = logging.getLogger(__name__)


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``.

    Only JSON files whose stem matches a table name are loaded, so the
    inventory fixtures (``cars.json``, ``search_results.json``) are ignored
    here and read directly by :mod:`lib.cars` instead.
    """

    table_definitions = {
        "users": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    address TEXT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    segment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "insert_statement": (
                "INSERT INTO users (name, email, phone, address, username, password, segment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "accounts": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    balance REAL,
                    type TEXT,
                    number TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO accounts (user_id, balance, type, number) VALUES (?, ?, ?, ?)"
            ),
        },
        "loans": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS loans (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    lender TEXT,
                    purpose TEXT,
                    principal REAL,
                    monthly_payment REAL,
                    remaining_months INTEGER,
                    interest_rate REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO loans (user_id, lender, purpose, principal, monthly_payment, "
                "remaining_months, interest_rate) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "reservations": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    reference TEXT UNIQUE,
                    car_model TEXT,
                    dealer_name TEXT,
                    car_price REAL,
                    reason TEXT,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO reservations (user_id, reference, car_model, dealer_name, "
                "car_price, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "appointments": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    reference TEXT UNIQUE,
                    dealer_name TEXT,
                    car_model TEXT,
                    date DATE,
                    start_time TIME,
                    end_time TIME,
                    purpose TEXT,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO appointments (user_id, reference, dealer_name, car_model, date, "
                "start_time, end_time, purpose, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "handoff_tickets": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS handoff_tickets (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    ticket_id TEXT UNIQUE,
                    reason TEXT,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO handoff_tickets (user_id, ticket_id, reason, status) "
                "VALUES (?, ?, ?, ?)"
            ),
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = Path(__file__).resolve().parent.parent
        self.database_path = database_path or (
            self.project_root_path / "data" / "autono.db"
        )
        self.source_data_path = self.project_root_path / "data" / "source"

        if not self.database_path.exists():
            self.connection = sqlite3.connect(":memory:")
            self.create_schema()
            self.load_data()
            self.save_to_disk()
            self.connection.close()

        # Always end up on the file-backed connection, so writes from tools
        # (reservations, appointments, tickets) survive the call.
        self.connection = sqlite3.connect(str(self.database_path))
        self.cursor = self.connection.cursor()

    def create_schema(self) -> None:
        for definition in self.table_definitions.values():
            self.connection.execute(definition["create_statement"])
        self.connection.commit()

    def load_data(self) -> None:
        for source_file in sorted(self.source_data_path.glob("*.json")):
            table_name = source_file.stem.lower()
            if table_name not in self.table_definitions:
                continue
            with open(source_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.insert_data(table_name, data)

    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> None:
        insert_statement = self.table_definitions[table_name]["insert_statement"]
        for row in data:
            self.connection.execute(insert_statement, tuple(row.values()))
        self.connection.commit()

    def save_to_disk(self) -> None:
        """Persist the freshly seeded in-memory database.

        Only valid while the connection is still ``:memory:`` — backing a
        file-backed connection up onto its own file deadlocks SQLite.
        """
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


def resolve_username(context_username: Optional[str] = None) -> str:
    """Return the active demo username (defaults to Alex Rivera)."""
    if context_username and str(context_username).strip():
        return str(context_username).strip()
    return DEMO_USERNAME


def get_user_id(db: Database, username: str) -> Optional[int]:
    row = db.run_query("SELECT id FROM users WHERE name = ?", (username,), one_record=True)
    return int(row[0]) if row else None
