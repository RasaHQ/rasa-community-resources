#!/usr/bin/env python3
"""Run the course's hand-written candidates through the factory into one folder, to practice reading a pool.

    python demo_pool.py pool

These seven runs are NOT an agent's work: each candidate was written by hand to isolate one property. A class
that does the real experiment fills a folder like this with its participants' runs instead.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = [
    ("tasks/a1-block-card.json", "block-card-good"),
    ("tasks/a1-block-card.json", "block-card-gate-omitted"),
    ("tasks/a1-block-card.json", "block-card-gate-false"),
    ("tasks/a1-block-card.json", "block-card-gate-deleted"),
    ("tasks/a2-rule-digits.json", "rule-digits-good"),
    ("tasks/a2-rule-digits.json", "rule-digits-nested"),
    ("tasks/a3-rule-confirm.json", "rule-confirm-on-digits"),
]


def main(pool):
    pool = Path(pool)
    for task, candidate in RUNS:
        run = pool / candidate
        if run.exists():
            print("refusing to reuse", run, file=sys.stderr)
            return 2
        result = subprocess.run([sys.executable, str(ROOT / "factory.py"), str(ROOT / task), str(ROOT / "candidates" / candidate), str(run)],
                                capture_output=True, text=True)
        print("%-26s %s" % (candidate, result.stdout.strip().split(" - ")[0]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
