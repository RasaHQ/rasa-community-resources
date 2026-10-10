"""SQLite mock operations backend for the dev-copilot demo."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_TECH_ID = "101"
DEMO_FIRST_NAME = "Alex"
DEMO_LAST_NAME = "Chen"
DEMO_BADGE_CODE = "4021"

logger = logging.getLogger(__name__)

PRIORITY_LABELS = {
    "emergency": "critical",
    "standard": "normal",
    "planned": "planned",
}


def _resolve_project_root() -> Path:
    """Locate the live project checkout, even inside a train-time snapshot.

    Rasa copies skill/tool/lib code into the model archive and runs it from
    there, so ``Path(__file__)`` can point at the snapshot copy rather than
    this repository. A real checkout is identifiable by ``agent.yml``: walk
    up from this file first, then from the working directory, and fall back
    to the legacy sibling-of-lib location.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "agent.yml").is_file():
            return candidate
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "agent.yml").is_file():
            return candidate
    return here.parent.parent


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

    table_definitions = {
        "technicians": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS technicians (
                    tech_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    badge_code TEXT NOT NULL
                )
            """,
            "insert_statement": (
                "INSERT INTO technicians (tech_id, first_name, last_name, badge_code) "
                "VALUES (?, ?, ?, ?)"
            ),
        },
        "service_calls": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS service_calls (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    call_ref TEXT NOT NULL UNIQUE,
                    building TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    issue TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    sla_minutes INTEGER NOT NULL,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO service_calls "
                "(tech_id, call_ref, building, unit_id, issue, priority, "
                "status, scheduled_at, sla_minutes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "parts": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS parts (
                    part_no TEXT PRIMARY KEY,
                    part_name TEXT NOT NULL,
                    unit_price REAL NOT NULL,
                    qty_on_hand INTEGER NOT NULL,
                    restricted INTEGER NOT NULL
                )
            """,
            "insert_statement": (
                "INSERT INTO parts (part_no, part_name, unit_price, qty_on_hand, restricted) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "parts_orders": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS parts_orders (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    call_ref TEXT NOT NULL,
                    order_id TEXT NOT NULL UNIQUE,
                    part_no TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO parts_orders "
                "(tech_id, call_ref, order_id, part_no, qty, status) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
        "support_tickets": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    ticket_id TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    system TEXT NOT NULL,
                    repro_steps TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO support_tickets "
                "(tech_id, ticket_id, summary, severity, system, repro_steps, "
                "status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "ticket_comments": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS ticket_comments (
                    id INTEGER PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    tech_id TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES support_tickets(ticket_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO ticket_comments "
                "(ticket_id, tech_id, comment, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
        },
        "deployments": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    deploy_ref TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    deployed_at TEXT NOT NULL,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO deployments "
                "(tech_id, project, environment, deploy_ref, status, deployed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
        "pull_requests": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS pull_requests (
                    id INTEGER PRIMARY KEY,
                    pr_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    project TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    reviewer_id TEXT,
                    status TEXT NOT NULL,
                    ci_status TEXT NOT NULL
                )
            """,
            "insert_statement": (
                "INSERT INTO pull_requests "
                "(pr_id, title, project, author_id, reviewer_id, status, ci_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "reminders": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    reminder_text TEXT NOT NULL,
                    due_minutes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO reminders "
                "(tech_id, reminder_text, due_minutes, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
        },
        "feedback": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY,
                    tech_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    expected TEXT,
                    actual TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(tech_id) REFERENCES technicians(tech_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO feedback "
                "(tech_id, category, severity, description, expected, actual, created_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = _resolve_project_root()
        self.database_path = database_path or (
            self.project_root_path / "data" / "operations.db"
        )
        self.source_data_path = self.project_root_path / "data" / "source"

        fresh = not self.database_path.exists()
        self.connection = sqlite3.connect(
            ":memory:" if fresh else str(self.database_path)
        )
        self.create_schema()
        self.migrate()
        if fresh:
            self.load_data()
        else:
            self.seed_empty_tables()
        if fresh:
            self.save_to_disk()

        self.cursor = self.connection.cursor()

    def create_schema(self) -> None:
        for definition in self.table_definitions.values():
            self.connection.execute(definition["create_statement"])
        self.connection.commit()

    def migrate(self) -> None:
        """Apply additive column changes to tables that predate this build."""
        support_columns = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA table_info(support_tickets)"
            ).fetchall()
        }
        if support_columns and "updated_at" not in support_columns:
            self.connection.execute(
                "ALTER TABLE support_tickets ADD COLUMN updated_at TEXT"
            )
            self.connection.commit()

    def load_data(self) -> None:
        for source_file in sorted(self.source_data_path.glob("*.json")):
            with open(source_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            table_name = source_file.stem.lower()
            if table_name in self.table_definitions:
                self.insert_data(table_name, data)

    def seed_empty_tables(self) -> None:
        """Seed any known table that is empty, using its JSON source file.

        Runs when opening an existing database so newer demo tables (for
        example ``support_tickets``) still receive their starter rows.
        """
        for source_file in sorted(self.source_data_path.glob("*.json")):
            table_name = source_file.stem.lower()
            if table_name not in self.table_definitions:
                continue
            count_row = self.connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()
            if count_row and int(count_row[0]) > 0:
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


def resolve_tech_id(context_tech_id: Optional[str] = None) -> str:
    """Return the active demo developer id (defaults to Alex / 101)."""
    if context_tech_id and str(context_tech_id).strip():
        return str(context_tech_id).strip()
    return DEMO_TECH_ID


def get_technician(
    db: Database, tech_id: str
) -> Optional[Tuple[str, str, str, str]]:
    row = db.run_query(
        "SELECT tech_id, first_name, last_name, badge_code "
        "FROM technicians WHERE tech_id = ?",
        (tech_id,),
        one_record=True,
    )
    return row  # type: ignore[return-value]


def get_part(db: Database, part_no: str) -> Optional[Tuple[str, str, float, int, int]]:
    row = db.run_query(
        "SELECT part_no, part_name, unit_price, qty_on_hand, restricted "
        "FROM parts WHERE UPPER(REPLACE(part_no, ' ', '')) = ?",
        (part_no.strip().upper().replace(" ", ""),),
        one_record=True,
    )
    return row  # type: ignore[return-value]


def next_order_id(db: Database) -> str:
    row = db.run_query(
        "SELECT COUNT(*) FROM parts_orders",
        one_record=True,
    )
    count = int(row[0]) if row else 0
    return f"ORP{1000 + count + 1}"
