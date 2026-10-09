"""Bounded read-only SQLite tools shared by both chat implementations."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
MAX_ROWS = 100
ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


def database_path() -> Path:
    return Path(os.environ.get("CHINOOK_DATABASE", ROOT / "data/chinook.sqlite")).resolve(strict=True)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    connection.enable_load_extension(False)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in ALLOWED else sqlite3.SQLITE_DENY)
    ticks = 0
    def bounded_work():
        nonlocal ticks
        ticks += 1
        return int(ticks > 1000)
    connection.set_progress_handler(bounded_work, 1000)
    return connection


def query(sql: str) -> dict:
    """Run one read-only statement; fail rather than silently truncate rows."""
    try:
        with closing(connect()) as connection:
            cursor = connection.execute(sql)
            columns = [item[0] for item in cursor.description or []]
            rows = cursor.fetchmany(MAX_ROWS + 1)
            if len(rows) > MAX_ROWS:
                return {"status": "error", "reason": "too_many_rows", "next_step": "Add LIMIT 100 or a narrower filter."}
            return {"status": "ok", "columns": columns, "rows": [list(row) for row in rows]}
    except sqlite3.Error as error:
        return {"status": "error", "reason": str(error), "next_step": "Use the schema to correct the query. Writes, attachments and PRAGMA are refused."}


def list_tables() -> dict:
    return query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")


def schema(table_names: str) -> dict:
    available = list_tables()
    known = {row[0] for row in available.get("rows", [])}
    names = [name.strip() for name in table_names.split(",")]
    if not names or not set(names).issubset(known):
        return {"status": "error", "reason": "unknown_table", "next_step": "List tables first and use exact returned names."}
    with closing(connect()) as connection:
        result = []
        for name in names:
            sql = connection.execute("SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (name,)).fetchone()[0]
            result.append({"table": name, "create_sql": sql})
        return {"status": "ok", "tables": result}


def check_query(sql: str) -> dict:
    """Compile without executing; this is not an LLM semantic checker."""
    result = query("EXPLAIN QUERY PLAN " + sql)
    return {"status": result["status"], "query": sql, **({"reason": result["reason"]} if result["status"] != "ok" else {})}
