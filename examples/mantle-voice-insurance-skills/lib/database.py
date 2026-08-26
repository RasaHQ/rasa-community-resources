"""SQLite mock insurance backend for the Poly voice demo."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

DEMO_CUSTOMER_ID = "123"
DEMO_FIRST_NAME = "Serena"
DEMO_USERNAME = "Serena Williams"
DATE_FORMAT = "%m/%d/%Y"

logger = logging.getLogger(__name__)


def find_project_root() -> Path:
    """Locate the workspace root that contains ``data/source`` seed fixtures.

    At runtime, ``lib/database.py`` may be imported from the extracted model
    snapshot (which does not include ``data/source``). Prefer the process cwd
    and walk parents so tools still seed against the live workspace.
    """
    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    candidates.append(cwd)
    candidates.extend(cwd.parents)
    here = Path(__file__).resolve().parent.parent
    candidates.append(here)
    candidates.extend(here.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "data" / "source").is_dir():
            return candidate
    return cwd

_DEFAULTS = (datetime(1900, 1, 1), datetime(2001, 2, 3))
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_WEEKDAY_RE = re.compile(
    r"(?:last |this |this past |past )?(" + "|".join(_WEEKDAYS) + r")"
)
_AGO_RE = re.compile(r"(?:(\d+)|a|an|one) (day|days|week|weeks) ago")

CLAIM_STATUS_LABELS = {
    0: "adjustor_pending",
    1: "adjustor_assigned",
    2: "inspection_scheduling",
    3: "accepted",
    4: "rejected",
    5: "not_found",
}


class Database:
    """In-memory-first SQLite store seeded from ``data/source/*.json``."""

    table_definitions = {
        "customers": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL
                )
            """,
            "insert_statement": (
                "INSERT INTO customers (customer_id, first_name, last_name) "
                "VALUES (?, ?, ?)"
            ),
        },
        "policies": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS policies (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    policy_type TEXT NOT NULL,
                    policy_num TEXT NOT NULL,
                    expiration_date TEXT,
                    premium REAL,
                    coverage_limit REAL,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO policies "
                "(customer_id, policy_type, policy_num, expiration_date, premium, coverage_limit) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
        "claims": {
            "create_statement": """
                CREATE TABLE IF NOT EXISTS claims (
                    id INTEGER PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL UNIQUE,
                    policy_num TEXT NOT NULL,
                    claim_date TEXT,
                    claim_status INTEGER NOT NULL,
                    inspection_date TEXT,
                    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
                )
            """,
            "insert_statement": (
                "INSERT INTO claims "
                "(customer_id, claim_id, policy_num, claim_date, claim_status, inspection_date) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
        },
    }

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.project_root_path = find_project_root()
        self.database_path = database_path or (
            self.project_root_path / "data" / "insurance.db"
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
    """Return the active demo customer id (defaults to Serena / 123)."""
    if context_customer_id and str(context_customer_id).strip():
        return str(context_customer_id).strip()
    return DEMO_CUSTOMER_ID


def customer_id_from_context(context: Any = None) -> str:
    """Resolve the active customer id from tool context with a safe demo fallback."""
    if context is None:
        return DEMO_CUSTOMER_ID
    try:
        return resolve_customer_id(context.memory.get("customer_id"))
    except Exception:
        return DEMO_CUSTOMER_ID


def get_customer(
    db: Database, customer_id: str
) -> Optional[Tuple[str, str, str]]:
    row = db.run_query(
        "SELECT customer_id, first_name, last_name FROM customers WHERE customer_id = ?",
        (customer_id,),
        one_record=True,
    )
    return row  # type: ignore[return-value]


def adjustor_date_from_claim(claim_date: str) -> str:
    """Return claim_date + 10 days in MM/DD/YYYY (source parity)."""
    try:
        parsed = datetime.strptime(claim_date, DATE_FORMAT)
    except ValueError:
        return claim_date
    return (parsed + timedelta(days=10)).strftime(DATE_FORMAT)


def _most_recent_weekday(today: datetime, target: int) -> datetime:
    delta = (today.weekday() - target) % 7
    if delta == 0:
        delta = 7
    return today - timedelta(days=delta)


def _resolve_relative(text: str, today: datetime) -> Optional[datetime]:
    t = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    if t == "today":
        return today
    if t == "yesterday":
        return today - timedelta(days=1)
    if t in ("day before yesterday", "the day before yesterday"):
        return today - timedelta(days=2)
    if t == "last week":
        return today - timedelta(days=7)
    m = _AGO_RE.fullmatch(t)
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        return today - timedelta(days=n * (7 if m.group(2).startswith("week") else 1))
    m = _WEEKDAY_RE.fullmatch(t)
    if m:
        return _most_recent_weekday(today, _WEEKDAYS[m.group(1)])
    return None


def normalize_incident_date(raw: str, today: Optional[datetime] = None) -> Optional[str]:
    """Normalize an incident date string to MM/DD/YYYY, or None if unparseable."""
    if not isinstance(raw, str) or not raw.strip():
        return None

    today = today or datetime.now()
    relative = _resolve_relative(raw, today)
    if relative is not None:
        return relative.strftime(DATE_FORMAT)

    try:
        from dateutil import parser as date_parser
    except ImportError:
        date_parser = None

    if date_parser is None:
        try:
            return datetime.strptime(raw.strip(), DATE_FORMAT).strftime(DATE_FORMAT)
        except ValueError:
            return None

    parsed = []
    for default in _DEFAULTS:
        try:
            parsed.append(date_parser.parse(raw, default=default, fuzzy=False))
        except (ValueError, OverflowError, TypeError):
            return None
    first, second = parsed
    if (first.year, first.month, first.day) != (second.year, second.month, second.day):
        return None
    return first.strftime(DATE_FORMAT)
