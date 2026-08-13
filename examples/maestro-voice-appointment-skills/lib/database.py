"""SQLite mock clinic backend for the Schedora voice demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_USERNAME = "Jamie Chen"

logger = logging.getLogger(__name__)


def find_project_root() -> Path:
    """Resolve the live agent project root (not a model-snapshot unpack path).

    Tools are loaded from the trained model archive, so ``Path(__file__)`` can
    point inside a temporary ``calm_v2_snapshot/`` that has ``lib/`` but no
    ``data/source/``. Prefer a directory that contains both ``agent.yml`` and
    seeded JSON so the SQLite demo backend stays populated under ``rasa run``.
    """
    markers = ("agent.yml",)
    search_bases = [Path.cwd(), Path(__file__).resolve().parent.parent]
    seen: set[Path] = set()
    for base in search_bases:
        for candidate in [base, *base.parents]:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if not all((resolved / marker).is_file() for marker in markers):
                continue
            source = resolved / "data" / "source"
            if source.is_dir() and any(source.glob("*.json")):
                return resolved
    return Path(__file__).resolve().parent.parent


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

    table_definitions = {
        "users": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    patient_id TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    date_of_birth TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "insert_statement": (
                "INSERT INTO users (name, patient_id, email, phone, date_of_birth) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "contacts": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    name TEXT,
                    handle TEXT,
                    relationship TEXT,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO contacts (user_id, name, handle, relationship) "
                "VALUES (?, ?, ?, ?)"
            ),
        },
        "appointments": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    doctor TEXT,
                    slot TEXT,
                    visit_reason TEXT,
                    status TEXT,
                    reference TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """,
            "insert_statement": (
                "INSERT INTO appointments (user_id, doctor, slot, visit_reason, status, reference) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
        "handoff_tickets": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS handoff_tickets (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    ticket_id TEXT,
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
        self.project_root_path = find_project_root()
        self.database_path = database_path or (
            self.project_root_path / "data" / "schedora.db"
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
    """Return the active demo username (defaults to Jamie Chen)."""
    if context_username and str(context_username).strip():
        return str(context_username).strip()
    return DEMO_USERNAME


def username_from_context(context=None) -> str:
    """Read the username straight off a tool context, falling back to the demo one."""
    if context is None:
        return DEMO_USERNAME
    return resolve_username(context.memory.get("username"))


def get_user_id(db: Database, username: str) -> Optional[int]:
    row = db.run_query("SELECT id FROM users WHERE name = ?", (username,), one_record=True)
    return int(row[0]) if row else None


def normalise_handle(handle: str) -> str:
    """Return a handle in canonical ``@Name`` form.

    Voice transcription rarely produces the '@', so accept it either way.
    """
    cleaned = str(handle or "").strip().lstrip("@").strip()
    return f"@{cleaned}" if cleaned else ""
