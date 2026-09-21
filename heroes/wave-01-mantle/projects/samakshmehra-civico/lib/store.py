"""The complaint store: a local SQLite file, seeded from ``data/*.json``.

There is no municipal API behind this and the demo says so out loud. What
matters for the demo is not that the data is real but that it is *consistent* —
a complaint number handed out during a call can be read back on the next call,
with the right officer, the right department and a target date that is
genuinely in the past or genuinely in the future.
"""

from __future__ import annotations

import functools
import json
import sqlite3
from datetime import date, timedelta

from lib.paths import data_dir, db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS citizens (
    citizen_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    phone      TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id     TEXT PRIMARY KEY,
    citizen_id       TEXT,
    phone            TEXT NOT NULL,
    category         TEXT NOT NULL,
    ward_id          TEXT NOT NULL,
    locality         TEXT NOT NULL,
    exact_spot       TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    department       TEXT NOT NULL,
    sla_days         INTEGER NOT NULL,
    created_on       TEXT NOT NULL,
    target_on        TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'registered',
    escalation_level INTEGER NOT NULL DEFAULT 1,
    resolution_note  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_complaints_phone ON complaints (phone);
CREATE INDEX IF NOT EXISTS idx_complaints_ward  ON complaints (ward_id, category);
CREATE TABLE IF NOT EXISTS supporting_reports (
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id),
    phone TEXT NOT NULL,
    exact_spot TEXT NOT NULL,
    description TEXT NOT NULL,
    created_on TEXT NOT NULL,
    PRIMARY KEY (complaint_id, phone)
);
"""

OPEN_STATUSES = ("registered", "assigned", "in_progress")

STATUS_SPOKEN = {
    "registered": "registered and waiting to be assigned",
    "assigned": "assigned to a field crew",
    "in_progress": "being worked on",
    "resolved": "resolved",
    "closed": "closed",
}


@functools.lru_cache(maxsize=1)
def _load(name: str) -> dict | list:
    with open(data_dir() / name, encoding="utf-8") as handle:
        return json.load(handle)


def routing() -> dict:
    return _load("routing.json")["categories"]


def escalation_levels() -> list[dict]:
    return _load("escalation.json")["levels"]


def categories() -> list[str]:
    return list(routing().keys())


#: What people actually say, mapped to the six keys. Without this, "street
#: light" normalises to "street_light", which is not a category, and the line
#: tells a caller it does not handle street lights — which it does.
_CATEGORY_ALIASES = {
    "street_light": "streetlight", "streetlights": "streetlight",
    "street_lights": "streetlight", "light": "streetlight",
    "lights": "streetlight", "lamp": "streetlight", "lamppost": "streetlight",
    "street_lamp": "streetlight",
    "road": "pothole", "potholes": "pothole", "damaged_road": "pothole",
    "broken_road": "pothole", "roads": "pothole",
    "water": "water_supply", "watersupply": "water_supply",
    "no_water": "water_supply", "water_leak": "water_supply",
    "water_leakage": "water_supply", "tap_water": "water_supply",
    "garbage_collection": "garbage", "trash": "garbage", "rubbish": "garbage",
    "waste": "garbage", "litter": "garbage", "dustbin": "garbage",
    "drain": "drainage", "drains": "drainage", "sewer": "drainage",
    "sewage": "drainage", "blocked_drain": "drainage", "overflow": "drainage",
    "stray_dogs": "stray_animals", "stray_dog": "stray_animals",
    "dogs": "stray_animals", "cattle": "stray_animals",
    "stray_cattle": "stray_animals", "animals": "stray_animals",
    "monkeys": "stray_animals",
}


def normalise_category(spoken: str) -> str:
    """Map what a caller said onto one of the six category keys.

    Shared, because it was not: living inside the report_problem tools, it
    meant "who handles potholes in Kavi Nagar" was told this line does not
    handle potholes, while "there is a pothole" filed one without complaint.
    """
    key = str(spoken or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    if key in routing():
        return key
    # People do not hand over a category, they hand over a phrase — "uncollected
    # garbage", "broken street light near me". Fall back to finding a known
    # word inside it, longest first so "street_light" wins over "light".
    words = set(key.split("_"))
    for candidate in sorted(set(_CATEGORY_ALIASES) | set(routing()),
                            key=len, reverse=True):
        parts = candidate.split("_")
        if all(part in words for part in parts):
            return _CATEGORY_ALIASES.get(candidate, candidate)
    return key


def say_ward(ward_id: str) -> str:
    """"W12" -> "12", for reading a ward number aloud."""
    stripped = str(ward_id or "").lstrip("W").lstrip("0")
    return stripped or str(ward_id)


def connect() -> sqlite3.Connection:
    """Open the demo database, creating and seeding it on first use."""
    fresh = not db_path().exists()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    if fresh:
        _seed(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    today = date.today()

    conn.executemany(
        "INSERT OR REPLACE INTO citizens (citizen_id, name, phone) VALUES (?, ?, ?)",
        [(c["citizen_id"], c["name"], c["phone"]) for c in _load("citizens.json")],
    )

    rows = []
    for c in _load("complaints.json")["complaints"]:
        # Ages, not dates. A complaint seeded with a fixed calendar date is on
        # time the week it is written and absurdly overdue three months later.
        created = today - timedelta(days=int(c["days_ago"]))
        target = created + timedelta(days=int(c["sla_days"]))
        rows.append((
            c["complaint_id"], c["citizen_id"], c["phone"], c["category"],
            c["ward_id"], c["locality"], c["exact_spot"], c["description"],
            c["department"], int(c["sla_days"]),
            created.isoformat(), target.isoformat(),
            c["status"], int(c["escalation_level"]), c["resolution_note"],
        ))
    conn.executemany(
        """INSERT OR REPLACE INTO complaints
           (complaint_id, citizen_id, phone, category, ward_id, locality,
            exact_spot, description, department, sla_days, created_on,
            target_on, status, escalation_level, resolution_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def citizen_by_phone(phone: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM citizens WHERE phone = ?", (str(phone),)
        ).fetchone()
    return dict(row) if row else None


def get_complaint(complaint_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM complaints WHERE complaint_id = ?",
            (str(complaint_id).upper().replace(" ", ""),),
        ).fetchone()
    return _decorate(dict(row)) if row else None


def complaints_for_phone(phone: str, open_only: bool = False) -> list[dict]:
    query = """SELECT * FROM complaints WHERE (phone = ? OR EXISTS (
        SELECT 1 FROM supporting_reports AS r
        WHERE r.complaint_id = complaints.complaint_id AND r.phone = ?))"""
    params: tuple = (str(phone), str(phone))
    if open_only:
        query += f" AND status IN ({','.join('?' * len(OPEN_STATUSES))})"
        params += OPEN_STATUSES
    query += " ORDER BY created_on DESC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_decorate(dict(r)) for r in rows]


def open_similar(category: str, ward_id: str) -> list[dict]:
    """Open complaints of the same kind in the same ward.

    Deliberately coarse. The earlier version of this project measured metres
    between two geocoded points to decide whether two reports were the same
    pothole, which is a precise answer to a question nobody can answer
    precisely. Same problem, same neighbourhood, still open — then ask the
    caller, who is the only one who actually knows.
    """
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM complaints
                WHERE category = ? AND ward_id = ?
                  AND status IN ({','.join('?' * len(OPEN_STATUSES))})
                ORDER BY created_on DESC""",
            (category, ward_id, *OPEN_STATUSES),
        ).fetchall()
    return [_decorate(dict(r)) for r in rows]


def _decorate(row: dict) -> dict:
    """Add the derived fields every caller-facing answer needs."""
    target = date.fromisoformat(row["target_on"])
    days_left = (target - date.today()).days
    is_open = row["status"] in OPEN_STATUSES
    row["days_left"] = days_left
    row["days_overdue"] = max(0, -days_left) if is_open else 0
    row["is_open"] = is_open
    row["is_overdue"] = is_open and days_left < 0
    row["status_spoken"] = STATUS_SPOKEN.get(row["status"], row["status"])
    row["spoken_id"] = spoken_id(row["complaint_id"])
    return row


def spoken_id(complaint_id: str) -> str:
    """"CIV1047" -> "C I V one zero four seven", for text-to-speech."""
    from lib.speech import say_reference

    return say_reference(complaint_id)


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def next_complaint_id() -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT complaint_id FROM complaints WHERE complaint_id LIKE 'CIV%' "
            "ORDER BY CAST(SUBSTR(complaint_id, 4) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
    highest = int(row["complaint_id"][3:]) if row else 1000
    return f"CIV{highest + 1}"


def insert_complaint(
    *, phone: str, category: str, ward_id: str, locality: str,
    exact_spot: str, description: str, department: str, sla_days: int,
    citizen_id: str | None = None,
) -> dict:
    today = date.today()
    target = today + timedelta(days=int(sla_days))
    with connect() as conn:
        # Allocation and insert share a write lock, including concurrent calls.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(complaint_id, 4) AS INTEGER)) FROM complaints"
        ).fetchone()
        complaint_id = f"CIV{(row[0] or 1000) + 1}"
        conn.execute(
            """INSERT INTO complaints
               (complaint_id, citizen_id, phone, category, ward_id, locality,
                exact_spot, description, department, sla_days, created_on,
                target_on, status, escalation_level, resolution_note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'registered',1,'')""",
            (complaint_id, citizen_id, str(phone), category, ward_id, locality,
             exact_spot, description, department, int(sla_days),
             today.isoformat(), target.isoformat()),
        )
        conn.commit()
    return get_complaint(complaint_id)


def raise_escalation(complaint_id: str) -> dict | None:
    """Move a complaint up one rung and extend its target date.

    Level 3 is the top. Calling this on an already-level-3 complaint returns it
    unchanged with ``already_top`` set, rather than inventing a fourth
    authority for someone who has run out of them.
    """
    row = get_complaint(complaint_id)
    if row is None:
        return None

    levels = escalation_levels()
    current = int(row["escalation_level"])
    if current >= len(levels):
        row["already_top"] = True
        row["authority"] = levels[-1]["authority"]
        row["authority_contact"] = levels[-1]["contact"]
        return row

    nxt = levels[current]  # levels are 1-based; index `current` is the next one
    new_target = date.today() + timedelta(days=int(nxt["extra_days"]))
    with connect() as conn:
        conn.execute(
            "UPDATE complaints SET escalation_level = ?, target_on = ? "
            "WHERE complaint_id = ?",
            (nxt["level"], new_target.isoformat(), row["complaint_id"]),
        )
        conn.commit()

    updated = get_complaint(row["complaint_id"])
    updated["already_top"] = False
    updated["authority"] = nxt["authority"]
    updated["authority_contact"] = nxt["contact"]
    return updated


def attach_report(complaint_id: str, phone: str, exact_spot: str,
                  description: str) -> dict | None:
    """Keep each supporting caller's report once, separately from resolution notes."""
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)
        ).fetchone()
        if row is None or row["status"] not in OPEN_STATUSES:
            return None
        conn.execute(
            """INSERT INTO supporting_reports VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(complaint_id, phone) DO UPDATE SET
               exact_spot = excluded.exact_spot, description = excluded.description""",
            (complaint_id, phone, exact_spot, description, date.today().isoformat()),
        )
    return get_complaint(complaint_id)


def attach_note(complaint_id: str, note: str) -> dict | None:
    """Record that another caller reported the same thing."""
    row = get_complaint(complaint_id)
    if row is None:
        return None
    existing = row["resolution_note"]
    merged = f"{existing}; {note}".strip("; ") if existing else note
    with connect() as conn:
        conn.execute(
            "UPDATE complaints SET resolution_note = ? WHERE complaint_id = ?",
            (merged, row["complaint_id"]),
        )
        conn.commit()
    return get_complaint(row["complaint_id"])
