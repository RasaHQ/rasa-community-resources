"""SQLite mock banking backend for the Rasano voice demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_USERNAME = "John Smith"

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Locate the project root that holds ``data/source``.

    At runtime tools may be loaded from an extracted model snapshot, where
    ``__file__`` points at a packaged copy without the seed data. The server
    always runs from the project root, so prefer the current working directory
    and only fall back to this file's location.
    """
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
    for base in candidates:
        for directory in [base, *base.parents]:
            if (directory / "data" / "source").is_dir():
                return directory
    return Path(__file__).resolve().parent.parent


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

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
                    sort_code TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO accounts (user_id, balance, type, number, sort_code) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "transactions": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER,
                    amount REAL,
                    datetime DATETIME,
                    description TEXT,
                    payment_method TEXT,
                    payee TEXT,
                    FOREIGN KEY(account_id) REFERENCES accounts(id)
                )
            """,
            "insert_statement": """
                INSERT INTO transactions (account_id, amount, datetime, description, payment_method, payee)
                VALUES (
                    ?,
                    ?,
                    datetime('now', '-' || (ABS(random()) % 90) || ' days',
                                    '-' || (ABS(random()) % 24) || ' hours',
                                    '-' || (ABS(random()) % 60) || ' minutes',
                                    '-' || (ABS(random()) % 60) || ' seconds'),
                    ?,
                    ?,
                    ?
                )
            """,
        },
        "payees": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS payees (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    name TEXT,
                    sort_code TEXT,
                    account_number TEXT,
                    type TEXT,
                    reference TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO payees (user_id, name, sort_code, account_number, type, reference) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
        "cards": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    account_id INTEGER,
                    number TEXT UNIQUE,
                    type TEXT,
                    status TEXT,
                    issued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(account_id) REFERENCES accounts(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO cards (user_id, account_id, number, type, status) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "branches": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS branches (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    distance_km REAL
                )
            """,
            "insert_statement": (
                "INSERT INTO branches (name, address, distance_km) VALUES (?, ?, ?)"
            ),
        },
        "advisors": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS advisors (
                    id INTEGER PRIMARY KEY,
                    branch_id INTEGER,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    position TEXT,
                    FOREIGN KEY(branch_id) REFERENCES branches(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO advisors (branch_id, name, email, phone, position) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "appointments": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY,
                    advisor_id INTEGER,
                    date DATE,
                    start_time TIME,
                    end_time TIME,
                    status TEXT,
                    FOREIGN KEY(advisor_id) REFERENCES advisors(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO appointments (advisor_id, date, start_time, end_time, status) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = _find_project_root()
        self.database_path = database_path or (
            self.project_root_path / "data" / "banking.db"
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


def resolve_username(context_username: Optional[str] = None) -> str:
    """Return the active demo username (defaults to John Smith)."""
    if context_username and str(context_username).strip():
        return str(context_username).strip()
    return DEMO_USERNAME


def username_from_context(context: Any = None) -> str:
    """Resolve the active customer name from project memory.

    A bare ``username`` read resolves to ``session.project.username`` (skill
    schemas do not declare it), which the session-start skill loads. Falls back
    to the demo customer when memory is empty.
    """
    if context is None:
        return DEMO_USERNAME
    return resolve_username(context.memory.get("username"))


def get_user_id(db: Database, username: str) -> Optional[int]:
    row = db.run_query("SELECT id FROM users WHERE name = ?", (username,), one_record=True)
    return int(row[0]) if row else None


def mask_card(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) < 4:
        return number
    return f"•••• {digits[-4:]}"
