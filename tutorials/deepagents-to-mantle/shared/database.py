"""Bounded read-only SQLite tools shared by both chat implementations."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
MAX_ROWS = 100
# Teaching defaults, not a token budget or a process-memory sandbox. SQLite's
# length limit also applies to its encoded rows, not only individual cells.
MAX_SQLITE_VALUE_BYTES = 16_384
MAX_RESULT_JSON_BYTES = 65_536
ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


def database_path() -> Path:
    return Path(os.environ.get("CHINOOK_DATABASE", ROOT / "data/chinook.sqlite")).resolve(strict=True)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    try:
        connection.enable_load_extension(False)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_SQLITE_VALUE_BYTES)
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
    except BaseException:
        # The caller's closing() context has not been entered if setup fails.
        connection.close()
        raise


def checked_result(result: dict) -> dict:
    """Require JSON values and bound one canonical successful result.

    The ASCII-escaped, compact JSON form defines this helper's byte budget.
    Framework envelopes, formatting and model tokenization are separate.
    Never stringify binary values or return a truncated, apparently complete
    answer. JSON's NaN/Infinity extensions are deliberately disabled.
    """
    try:
        encoded = json.dumps(result, ensure_ascii=True, allow_nan=False,
                             separators=(",", ":"))
    except (TypeError, ValueError):
        return {"status": "error", "reason": "unsupported_result_value",
                "next_step": "Select text and finite numeric values; binary values need an explicit representation."}
    if len(encoded.encode("utf-8")) > MAX_RESULT_JSON_BYTES:
        return {"status": "error", "reason": "result_too_large",
                "next_step": "Select fewer columns or smaller values. A row limit alone may not reduce the result enough."}
    return result


def query_error(error: sqlite3.Error) -> dict:
    if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_TOOBIG:
        return {"status": "error", "reason": "sqlite_value_too_large",
                "next_step": "Select smaller values or fewer columns; SQLite also limits encoded row length."}
    return {"status": "error", "reason": str(error)[:240], "next_step": "Use the schema to correct the query. Writes, attachments and PRAGMA are refused."}


def query(sql: str) -> dict:
    """Run one read-only statement; fail rather than silently truncate rows."""
    try:
        with closing(connect()) as connection:
            cursor = connection.execute(sql)
            columns = [item[0] for item in cursor.description or []]
            rows = cursor.fetchmany(MAX_ROWS + 1)
            if len(rows) > MAX_ROWS:
                return {"status": "error", "reason": "too_many_rows", "next_step": "Add LIMIT 100 or a narrower filter."}
            return checked_result({"status": "ok", "columns": columns, "rows": [list(row) for row in rows]})
    except sqlite3.Error as error:
        return query_error(error)


def list_tables() -> dict:
    return query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")


def schema(table_names: str) -> dict:
    available = list_tables()
    if available["status"] != "ok":
        return available
    known = {row[0] for row in available.get("rows", [])}
    names = [name.strip() for name in table_names.split(",")]
    if not names or not set(names).issubset(known):
        return {"status": "error", "reason": "unknown_table", "next_step": "List tables first and use exact returned names."}
    try:
        with closing(connect()) as connection:
            result = []
            for name in names:
                sql = connection.execute("SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (name,)).fetchone()[0]
                result.append({"table": name, "create_sql": sql})
            return checked_result({"status": "ok", "tables": result})
    except sqlite3.Error as error:
        return query_error(error)


def check_query(sql: str) -> dict:
    """Compile without executing; this is not an LLM semantic checker."""
    result = query("EXPLAIN QUERY PLAN " + sql)
    return checked_result({"status": result["status"], "query": sql, **({"reason": result["reason"]} if result["status"] != "ok" else {})})
