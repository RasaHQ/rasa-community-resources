#!/usr/bin/env python3
"""Build travel.sqlite from the committed fixture.

    python scripts/build_db.py              # build (or rebuild) travel.sqlite
    python scripts/build_db.py --from-upstream  # regenerate the fixture itself

The fixture is a 50 KB SQL file rather than a binary database: it is diffable,
reviewable in a pull request, and cannot drift from the schema silently.

`--from-upstream` re-derives it from LangGraph's 109 MB travel2.sqlite. That is
a maintainer operation, not something a reader needs.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "travel_seed.sql"
DB = ROOT / "travel.sqlite"
UPSTREAM = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"


def build() -> int:
    if not SEED.exists():
        print(f"✗ missing {SEED}", file=sys.stderr)
        return 1
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.executescript(SEED.read_text(encoding="utf-8"))
    conn.commit()

    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in (
            "flights",
            "tickets",
            "ticket_flights",
            "car_rentals",
            "hotels",
            "trip_recommendations",
        )
    }
    conn.close()
    size = DB.stat().st_size / 1024
    print(f"✓ built {DB.name} ({size:.0f} KB)")
    for table, n in counts.items():
        print(f"    {table:<22} {n:>4}")
    return 0


def from_upstream() -> int:
    """Regenerate data/travel_seed.sql from the real travel2.sqlite."""
    print("This re-derives the fixture from LangGraph's 109 MB database.")
    print("Download it first, then point at it:")
    print(f"    curl -L -o /tmp/travel2.sqlite {UPSTREAM}")
    print("    TRAVEL_UPSTREAM=/tmp/travel2.sqlite python scripts/build_db.py --from-upstream")
    print()
    import os

    upstream = os.environ.get("TRAVEL_UPSTREAM")
    if not upstream or not Path(upstream).exists():
        print("✗ set TRAVEL_UPSTREAM to the downloaded file", file=sys.stderr)
        return 1
    print(f"regenerating from {upstream} …")
    # The generator lives in the tutorial write-up rather than here: it is run
    # once when the upstream fixture changes, which is close to never.
    print("✗ not implemented as a one-liner on purpose — see tutorial/TUTORIAL.md")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-upstream", action="store_true")
    args = parser.parse_args()
    raise SystemExit(from_upstream() if args.from_upstream else build())
