#!/usr/bin/env python3
"""Set the limit in your task, and make the builder's attempt again if there is one.

    python set_limit.py 2        (a number from 1 to 3)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv):
    if len(argv) != 1 or argv[0] not in ("1", "2", "3"):
        print("Use a number from 1 to 3, for example: python set_limit.py 2")
        return 2
    path = ROOT / "tasks" / "b-limit-currencies.json"
    task = json.loads(path.read_text())
    task["limit"] = int(argv[0])
    path.write_text(json.dumps(task, indent=2) + "\n")
    print("limit is now", argv[0])
    if (ROOT / "attempts" / "mine").exists():
        subprocess.run([sys.executable, str(ROOT / "scripted_builder.py"), "tasks/b-limit-currencies.json", "attempts/mine"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
