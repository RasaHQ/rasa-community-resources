"""SQLite mock telecom backend for the Telano voice demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_USERNAME = "Serena Williams"
DEMO_CUSTOMER_ID = "123"
SPEED_THRESHOLD_MBPS = 100

logger = logging.getLogger(__name__)


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

    table_definitions = {
        "customers": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    plan_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "insert_statement": (
                "INSERT INTO customers "
                "(customer_id, first_name, last_name, name, email, phone, address, plan_name) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            "columns": [
                "customer_id",
                "first_name",
                "last_name",
                "name",
                "email",
                "phone",
                "address",
                "plan_name",
            ],
        },
        "billing": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS billing (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    source TEXT NOT NULL,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO billing (customer_id, date, amount, source) VALUES (?, ?, ?, ?)"
            ),
            "columns": ["customer_id", "date", "amount", "source"],
        },
        "routers": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS routers (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    device_id TEXT UNIQUE NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    wifi_name TEXT,
                    last_reset_at DATETIME,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO routers (customer_id, device_id, model, status, wifi_name) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            "columns": ["customer_id", "device_id", "model", "status", "wifi_name"],
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = Path(__file__).resolve().parent.parent
        self.database_path = database_path or (
            self.project_root_path / "data" / "telco.db"
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
        definition = self.table_definitions[table_name]
        insert_statement = definition["insert_statement"]
        columns = definition["columns"]
        for row in data:
            values = tuple(row[column] for column in columns)
            self.connection.execute(insert_statement, values)
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


def resolve_username(context_username: Optional[str] = None) -> str:
    """Return the active demo username (defaults to Serena Williams)."""
    if context_username and str(context_username).strip():
        return str(context_username).strip()
    return DEMO_USERNAME


def resolve_customer_id(context_customer_id: Optional[str] = None) -> str:
    """Return the active demo customer id (defaults to 123)."""
    if context_customer_id and str(context_customer_id).strip():
        return str(context_customer_id).strip()
    return DEMO_CUSTOMER_ID


def username_from_context(context=None) -> str:
    """Resolve the active customer display name from project memory."""
    if context is None:
        return DEMO_USERNAME
    return resolve_username(context.memory.get("username"))


def customer_id_from_context(context=None) -> str:
    """Resolve the active customer id from project memory."""
    if context is None:
        return DEMO_CUSTOMER_ID
    return resolve_customer_id(context.memory.get("customer_id"))


def get_customer_by_name(db: Database, username: str) -> Optional[Tuple]:
    return db.run_query(
        """
        SELECT customer_id, first_name, last_name, name, email, address, plan_name
        FROM customers WHERE name = ?
        """,
        (username,),
        one_record=True,
    )


def get_customer_by_id(db: Database, customer_id: str) -> Optional[Tuple]:
    return db.run_query(
        """
        SELECT customer_id, first_name, last_name, name, email, address, plan_name
        FROM customers WHERE customer_id = ?
        """,
        (customer_id,),
        one_record=True,
    )


MONTH_ALIASES = {
    "jan": "January",
    "january": "January",
    "feb": "February",
    "february": "February",
    "mar": "March",
    "march": "March",
    "apr": "April",
    "april": "April",
    "may": "May",
    "jun": "June",
    "june": "June",
    "jul": "July",
    "july": "July",
    "aug": "August",
    "august": "August",
    "sep": "September",
    "sept": "September",
    "september": "September",
    "oct": "October",
    "october": "October",
    "nov": "November",
    "november": "November",
    "dec": "December",
    "december": "December",
}


def normalize_month(month_text: str) -> Optional[str]:
    """Normalize a free-text month to a full English month name."""
    if not month_text:
        return None
    key = str(month_text).strip().lower()
    return MONTH_ALIASES.get(key)


def month_to_billing_date(month_text: str, year: int = 2026) -> Optional[str]:
    """Map a month name to MM/01/YYYY matching seed billing dates."""
    from datetime import datetime

    month = normalize_month(month_text)
    if not month:
        return None
    try:
        date_obj = datetime.strptime(f"{month} {year}", "%B %Y")
        return date_obj.strftime("%m/%d/%Y")
    except ValueError:
        return None
