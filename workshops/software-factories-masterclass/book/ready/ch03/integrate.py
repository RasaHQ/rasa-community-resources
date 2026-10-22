#!/usr/bin/env python3
"""Integration: put an accepted change into the product, then replay the checks on the result.

    python integrate.py --record-base                                         remember the product you start from
    python integrate.py tasks/a6-market-watchlist.json candidates/market-good integrate a candidate
Exit 0 integrated, 1 refused, 2 could not run.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRACKED = "product/briefing/market_card.py"


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv):
    if argv == ["--record-base"]:
        (ROOT / "base.json").write_text(json.dumps({TRACKED: fingerprint(ROOT / TRACKED)}, indent=2) + "\n")
        print("recorded the base product")
        return 0
    task_path, candidate = argv
    base = json.loads((ROOT / "base.json").read_text())
    # 1. the gate must say ACCEPT
    gate = subprocess.run([sys.executable, str(ROOT / "run_a6.py"), task_path, candidate], capture_output=True, text=True)
    if gate.returncode != 0:
        print("REFUSED: the gate did not accept this change:", gate.stdout.strip()[:160])
        return 1
    # 2. a stale base: the product must still be the one the change was made against
    if fingerprint(ROOT / TRACKED) != base[TRACKED]:
        print("REFUSED: stale base. The product has changed since this change was made.")
        return 1
    # 3. copy the allowed files in, then replay the checks on the integrated product
    task = json.loads((ROOT / task_path).read_text())
    for rel in task["allowed_paths"]:
        src = Path(candidate) / rel
        if src.is_dir():
            shutil.copytree(src, ROOT / rel, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, ROOT / rel)
    replay = subprocess.run([sys.executable, "-I", str(ROOT / task["acceptance"]["path"])], capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PRODUCT_PROJECT": str(ROOT / "product"), "PYTHONDONTWRITEBYTECODE": "1"})
    ok = replay.returncode == 0 and replay.stderr.strip().splitlines()[-1] == "OK"
    record = {"decision": "INTEGRATED" if ok else "ROLLED BACK", "candidate": str(candidate),
              "protected_suite_sha256": fingerprint(ROOT / task["acceptance"]["path"]), "tracked_file_sha256": fingerprint(ROOT / TRACKED)}
    (ROOT / "decisions").mkdir(exist_ok=True)
    (ROOT / "decisions" / "integration.json").write_text(json.dumps(record, indent=2) + "\n")
    print(record["decision"], "-", "the checks replayed on the integrated product" if ok else "the replay failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
