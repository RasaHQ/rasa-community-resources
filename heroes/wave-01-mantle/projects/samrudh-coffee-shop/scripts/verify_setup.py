#!/usr/bin/env python3
"""Pre-flight diagnostics for Artisan Roast Coffee Shop AI Agent."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    print("python-dotenv is not installed. Run: make install")
    sys.exit(1)

_TTY = sys.stdout.isatty()


def _c(code: str) -> str:
    return code if _TTY else ""


GREEN = _c("\033[92m")
YELLOW = _c("\033[93m")
RED = _c("\033[91m")
BLUE = _c("\033[94m")
MAGENTA = _c("\033[95m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
RESET = _c("\033[0m")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗  {msg}{RESET}")


def hint(msg: str) -> None:
    print(f"{DIM}       → {msg}{RESET}")


def section(title: str) -> None:
    print(f"\n{BLUE}{BOLD}{'─' * 62}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─' * 62}{RESET}")


def mask(value: str) -> str:
    if len(value) > 12:
        return f"{value[:4]}...{value[-4:]}"
    return "***"


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def error(self, msg: str, hint_msg: str | None = None) -> None:
        fail(msg)
        if hint_msg:
            hint(hint_msg)
        self.errors += 1

    def warning(self, msg: str, hint_msg: str | None = None) -> None:
        warn(msg)
        if hint_msg:
            hint(hint_msg)
        self.warnings += 1

    def success(self, msg: str) -> None:
        ok(msg)


def check_python_environment(rep: Report) -> None:
    section("1. Python & Dependencies")
    v = sys.version_info
    py_ver = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and 11 <= v.minor <= 14:
        rep.success(f"Python {py_ver} (compatible with Rasa Pro Mantle)")
    else:
        rep.warning(f"Python {py_ver} (recommended: >=3.11, <=3.14)")

    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        rep.success(f"SSL certificate bundle active ({certifi.where()})")
    except ImportError:
        rep.warning("certifi package not imported; may encounter macOS SSL certificate errors.")

    for pkg in ("rasa", "dotenv", "sentence_transformers", "pandas", "openpyxl"):
        if importlib.util.find_spec(pkg) is not None:
            rep.success(f"Package '{pkg}' is installed")
        else:
            rep.error(f"Missing required package '{pkg}'", "Run: make install")


def check_rasa_license(rep: Report) -> None:
    section("2. Rasa Pro License")
    key = os.environ.get("RASA_LICENSE", "").strip()
    if not key:
        rep.error("RASA_LICENSE is missing from .env", "Add your Rasa Pro license token to coffee-shop/.env")
        return

    rep.success(f"RASA_LICENSE present: {mask(key)}")
    try:
        parts = key.split(".")
        if len(parts) >= 2:
            payload_bytes = parts[1]
            padded = payload_bytes + "=" * (-len(payload_bytes) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            exp = payload.get("exp")
            if exp:
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                now_dt = datetime.now(tz=timezone.utc)
                if exp_dt > now_dt:
                    days_left = (exp_dt - now_dt).days
                    rep.success(f"License valid (expires in {days_left} days on {exp_dt.strftime('%Y-%m-%d')})")
                else:
                    rep.error(f"License expired on {exp_dt.strftime('%Y-%m-%d')}")
            scope = payload.get("scope", "")
            if "voice" in scope:
                rep.success("License includes Rasa Voice capability")
    except Exception as exc:
        rep.warning(f"Could not parse JWT license payload: {exc}")


def check_providers(rep: Report) -> None:
    section("3. AI Providers & Connectivity")
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        rep.success(f"GEMINI_API_KEY present: {mask(gemini_key)}")
    else:
        rep.error("GEMINI_API_KEY is missing from .env", "Add your Google Gemini API key.")

    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if deepgram_key:
        rep.success(f"DEEPGRAM_API_KEY present: {mask(deepgram_key)} (Voice ready)")
    else:
        rep.warning("DEEPGRAM_API_KEY not set (Text inspector only, voice disabled).")


def check_database(rep: Report) -> None:
    section("4. Coffee Shop SQLite Database")
    db_path = ROOT / "data" / "coffeeshop.db"
    if not db_path.is_file():
        rep.error(f"Database not found at {db_path}", "Run: make reset-db")
        return

    rep.success(f"Found database at {db_path.name}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    tables = ["transactions", "customers", "raw_materials", "product_recipes", "store_inventory", "active_orders"]
    for tbl in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
            count = cursor.fetchone()[0]
            rep.success(f"Table '{tbl}': {count:,} records")
        except sqlite3.OperationalError as e:
            rep.error(f"Table '{tbl}' missing or corrupted: {e}")

    conn.close()


def main() -> int:
    print(f"\n{MAGENTA}{BOLD}☕ Artisan Roast AI Agent — Pre-flight Diagnostics{RESET}")
    rep = Report()

    check_python_environment(rep)
    check_rasa_license(rep)
    check_providers(rep)
    check_database(rep)

    section("Summary")
    if rep.errors == 0:
        print(f"\n{GREEN}{BOLD}✓ ALL CHECKS PASSED ({rep.warnings} warnings){RESET}")
        print("Ready for: make validate && make train && make inspect")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ {rep.errors} check(s) failed.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
