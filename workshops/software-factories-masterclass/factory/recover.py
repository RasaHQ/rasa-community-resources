#!/usr/bin/env python3
"""Run the factory so that a stall, a crash or a duplicate request cannot be mistaken for a verdict.

    python recover.py <task.json> <candidate-dir> <ledger.json> [--deadline SECONDS] [--max-attempts N]

One key per piece of work: the task id plus the candidate's digest.
  - A decided key (ACCEPT or REJECT) is final. Asking again returns the stored decision and runs nothing.
  - A stalled or crashed attempt is recorded with its own number and retried, up to --max-attempts.
  - A REJECT is never retried: running a hidden suite again and again leaks it.
  - Out of attempts means ESCALATE: a person decides. The ledger says why.
Exit 0 ACCEPT, 1 REJECT, 4 ESCALATE, 2 could not run.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from factory import ROOT, digest_tree


def attempt(task, candidate, run_dir, deadline):
    proc = subprocess.Popen([sys.executable, str(ROOT / "factory.py"), task, str(candidate), str(run_dir)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=deadline)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)  # the factory and the test process it started
        proc.communicate()
        return "STALLED", "no verdict within %s seconds; the process group was killed" % deadline
    decision = run_dir / "decision.json"
    if proc.returncode in (0, 1) and decision.exists():
        return json.loads(decision.read_text())["decision"], out.strip()
    return "CRASHED", "exit %s with no decision record: %s" % (proc.returncode, (err.strip().splitlines() or ["?"])[-1])


def main(task, candidate, ledger_path, deadline=120.0, max_attempts=2):
    task_id = json.loads(Path(task).read_text())["id"]
    key = "%s:%s" % (task_id, digest_tree(candidate))
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    entry = ledger.setdefault(key, {"attempts": [], "final": None})
    if entry["final"]:
        print("DUPLICATE - already decided %s (attempt %d); nothing was run" % (entry["final"], len(entry["attempts"])))
        return {"ACCEPT": 0, "REJECT": 1}.get(entry["final"], 4)
    while len(entry["attempts"]) < max_attempts:
        n = len(entry["attempts"]) + 1
        run_dir = Path(tempfile.mkdtemp(prefix="attempt-")) / "run"
        outcome, note = attempt(task, candidate, run_dir, deadline)
        entry["attempts"].append({"n": n, "outcome": outcome, "note": note})
        print("attempt %d: %s - %s" % (n, outcome, note))
        if outcome in ("ACCEPT", "REJECT"):
            entry["final"] = outcome
            break
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    if not entry["final"]:
        entry["final"] = "ESCALATE"
        print("ESCALATE - %d attempts without a verdict; a person decides" % len(entry["attempts"]))
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    return {"ACCEPT": 0, "REJECT": 1}.get(entry["final"], 4)


if __name__ == "__main__":
    args, opts, it = [], {}, iter(sys.argv[1:])
    for a in it:
        if a == "--deadline":
            opts["deadline"] = float(next(it))
        elif a == "--max-attempts":
            opts["max_attempts"] = int(next(it))
        else:
            args.append(a)
    if len(args) != 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(*args, **opts))
