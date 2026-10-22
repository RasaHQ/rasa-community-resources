#!/usr/bin/env python3
"""Local stand-in for the factory's gate on task A6, for the teaching pack. The real driver is the factory's.

    python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
Gates in order: protected files (hash and presence), allowed paths, the protected acceptance suite.
Exit 0 ACCEPT, 1 REJECT, 2 could not run.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(task_path, candidate):
    task = json.loads(Path(task_path).read_text())
    candidate = Path(candidate)
    reasons = []
    pinned = [task["acceptance"], *task.get("support", [])]
    for item in pinned:
        if sha(ROOT / item["path"]) != item["sha256"]:
            print("could not run: the protected file", item["path"], "does not match its pin"); return 2
    for item in pinned:
        if (candidate / item["path"]).exists():
            reasons.append("protected file edited: " + item["path"])
    links = [str(p.relative_to(candidate)) for p in candidate.rglob("*") if p.is_symlink()]
    if links:
        print("REJECT - the candidate contains symbolic links:", ", ".join(links)); return 1
    changed = [str(p.relative_to(candidate)) for p in candidate.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for rel in changed:
        if rel in [i["path"] for i in pinned]:
            continue
        if not any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in task["allowed_paths"]):
            reasons.append("changed a file outside the allowed paths: " + rel)
    if reasons:
        print("REJECT -", "; ".join(reasons)); return 1
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "product"
        shutil.copytree(ROOT / "product", work)
        shutil.copytree(candidate / "product", work, dirs_exist_ok=True)
        done = subprocess.run([sys.executable, "-I", str(ROOT / task["acceptance"]["path"])], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin", "PRODUCT_PROJECT": str(work), "PYTHONDONTWRITEBYTECODE": "1"}, timeout=180)
        tail = done.stderr.strip().splitlines()
        ran = [l for l in tail if l.startswith("Ran ")]
        ok = done.returncode == 0 and ran and not ran[0].startswith("Ran 0 ") and tail[-1] == "OK"
        failing = [l.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "") for l in tail if l.startswith(("FAIL:", "ERROR:"))]
        if ok:
            print("ACCEPT - protected acceptance passed (" + ran[0] + ")"); return 0
        print("REJECT - the protected acceptance suite failed:", ", ".join(failing) or tail[-1]); return 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
