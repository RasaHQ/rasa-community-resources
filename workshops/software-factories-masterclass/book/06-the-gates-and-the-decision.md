# Chapter 6: The gates and the decision

**Goal:** build the part of the factory that judges an attempt: the gates, in order, and the written decision. Then run it on a good attempt and three bad ones.

**You need first:** Chapter 4. Chapter 5 builds the builder, and you don't need it here: this chapter judges attempts that are already written. Start from your `my-factory`, or copy `checkpoints/ch4` (see Chapter 3 for how). In a terminal, move into `my-factory` and activate your environment first:

```
cd my-factory
source .venv/bin/activate
```


**You build:** the gate runner, `run_a6.py`, and four attempts to judge.

## Words used in this chapter
- **Attempt:** one try at the task, kept as a folder with only the files it changed.
- **Gate:** one check an attempt must pass before the next check runs.
- **Decision:** ACCEPT (every gate passed), REJECT (a gate failed, and the decision names it) or could not run (the machine has a problem, which isn't the same as a wrong attempt).
- **Exit code:** the number a program gives back when it finishes. 0 is success, 1 is rejected and 2 is could not run.
- **Candidate:** the name the code uses for an attempt.

## The gates, in order
1. The fingerprints of the protected files must match the task. If they don't, nothing runs and the answer is exit code 2, could not run.
2. The attempt must not hold its own copy of a protected file, and must not hold any symbolic link. A copy of the tests would be an edit of the tests.
3. The attempt may change only the allowed paths.
4. The protected tests must pass, and the test run must end with its own closing lines (how many tests ran, and OK). That stops an attempt from ending the run early and pretending.

## Steps

1. Create the gate runner, `run_a6.py`, in `my-factory`:
```python
#!/usr/bin/env python3
"""Local stand-in for the factory's gate on task A6, for the teaching pack. The real driver is the factory's.

    python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
    python run_a6.py tasks/a6-market-watchlist.json baseline        # the product with nothing built: REJECT
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
    baseline = candidate == "baseline"  # judge the product as it is, with no candidate change
    candidate = ROOT / "candidates" / "_baseline_none" if baseline else Path(candidate)
    reasons = []
    pinned = [task["acceptance"], *task.get("support", [])]
    for item in pinned:
        if sha(ROOT / item["path"]) != item["sha256"]:
            print("could not run: the protected file", item["path"], "does not match its pin"); return 2
    for item in pinned:
        if not baseline and (candidate / item["path"]).exists():
            reasons.append("protected file edited: " + item["path"])
    links = [] if baseline else [str(p.relative_to(candidate)) for p in candidate.rglob("*") if p.is_symlink()]
    if links:
        print("REJECT - the candidate contains symbolic links:", ", ".join(links)); return 1
    changed = [] if baseline else [str(p.relative_to(candidate)) for p in candidate.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
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
        if not baseline:
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
```

2. Bring in the four attempts to judge. They are in the finished factory in the repository. `REPO` is the folder where you cloned it, for example `export REPO=~/rasa-community-resources`. From inside `my-factory`:
```
cp -R "$REPO"/workshops/software-factories-masterclass/factory/a6-market-watchlist/candidates candidates
```

   (The folder is called `candidates` because that is its name in the finished factory. Each folder is one attempt.)
   - `market-good` asks the card reader and adds nothing.
   - `market-shows-live` rewrites the daily rate as a live quote.
   - `market-invents-on-failure` shows typical rates when the source fails.
   - `market-edits-suite` carries its own copy of the tests.
3. Judge the good attempt:
```
python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
```

   You see: `ACCEPT - protected acceptance passed (Ran 14 tests in ...)`.
4. Judge a bad attempt, and read which check stopped it:
```
python run_a6.py tasks/a6-market-watchlist.json candidates/market-shows-live
```

   You see `REJECT` and the names of the failing checks, such as `test_k3_the_card_says_not_a_live_quote...`.
5. Judge the other two. `market-invents-on-failure` is rejected by the failure checks (K5 and K6). `market-edits-suite` is rejected at gate 2, before any test runs: `protected file edited`.

## You are done when
From inside `my-factory`, with your environment active, this prints `ch6 OK`:
```
T=tasks/a6-market-watchlist.json
python run_a6.py $T candidates/market-good > /dev/null \
 && ! python run_a6.py $T candidates/market-shows-live > /dev/null \
 && ! python run_a6.py $T candidates/market-invents-on-failure > /dev/null \
 && ! python run_a6.py $T candidates/market-edits-suite > /dev/null \
 && echo "ch6 OK"
```

At the start of this chapter `run_a6.py` doesn't exist, so it fails.

## Checkpoint
`checkpoints/ch6/`: your factory with a task, tests, gates and four attempts.

## If it fails
- `could not run: the protected file ... does not match its pin`: the fingerprints in the task don't match the files. Run the pinning step of Chapter 4 again.
- An attempt is accepted that should be rejected: gate 4 needs the closing lines of the test run, so check you pasted `run_a6.py` completely.
