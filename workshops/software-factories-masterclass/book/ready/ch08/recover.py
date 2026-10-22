#!/usr/bin/env python3
"""Run the factory so that a stall, a crash or a duplicate request cannot be mistaken for a verdict.

    python recover.py <task.json> <candidate-dir> <ledger.json> [--deadline SECONDS] [--max-attempts N]

One key per piece of work: task, candidate, baseline, verifier, suite and runtime fingerprints.
Single local writer only. A crash after execution but before recording can repeat work;
this teaching ledger is not an exactly-once distributed scheduler.
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

import hashlib
import platform
from factory_engine.factory import digest_tree

ROOT = Path(__file__).resolve().parent


def attempt(task, candidate, run_dir, deadline):
    proc = subprocess.Popen([sys.executable, str(ROOT / "judge.py"), task, str(candidate), str(run_dir)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=deadline)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.communicate()
        return "STALLED", "no verdict within %s seconds; the process group was killed" % deadline
    decision = run_dir / "decision.json"
    if proc.returncode in (0, 1) and decision.exists():
        return json.loads(decision.read_text())["decision"], out.strip()
    return "CRASHED", "exit %s with no decision record: %s" % (proc.returncode, (err.strip().splitlines() or ["?"])[-1])


def save_ledger(path, ledger):
    descriptor, temporary = tempfile.mkstemp(prefix='.ledger-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as output:
            json.dump(ledger, output, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(task, candidate, ledger_path, deadline=120.0, max_attempts=2):
    if type(max_attempts) is not int or max_attempts not in (1, 2, 3) or deadline <= 0:
        print("Could not run: use 1 to 3 attempts and a positive deadline.")
        return 2
    task = str(Path(task).resolve())
    candidate = Path(candidate).resolve()
    task_id = json.loads(Path(task).read_text())["id"]
    # A changed task, verifier, baseline or environment is different work.
    context = {"task_sha256": hashlib.sha256(Path(task).read_bytes()).hexdigest(),
               "candidate_sha256": digest_tree(candidate), "baseline_sha256": digest_tree(ROOT / "product"),
               "python": platform.python_version(),
               "verifier_sha256": hashlib.sha256((ROOT / "factory_engine/factory.py").read_bytes()).hexdigest(),
               "profile_sha256": hashlib.sha256((ROOT / "environment.json").read_bytes()).hexdigest(),
               "suite_sha256": hashlib.sha256((ROOT / "acceptance/c_recovery_policy.py").read_bytes()).hexdigest()}
    key = task_id + ":" + hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    entry = ledger.setdefault(key, {"attempts": [], "final": None, "context": context})
    if entry["final"]:
        print("DUPLICATE - already decided %s (attempt %d); nothing was run" % (entry["final"], len(entry["attempts"])))
        return {"ACCEPT": 0, "REJECT": 1}.get(entry["final"], 4)
    while len(entry["attempts"]) < max_attempts:
        n = len(entry["attempts"]) + 1
        scratch = ledger_path.parent / "recovery-runs"
        scratch.mkdir(exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="attempt-", dir=scratch)) / "run"
        outcome, note = attempt(task, candidate, run_dir, deadline)
        entry["attempts"].append({"n": n, "outcome": outcome, "note": note})
        print("attempt %d: %s - %s" % (n, outcome, note))
        if outcome in ("ACCEPT", "REJECT"):
            entry["final"] = outcome
            break
        save_ledger(ledger_path, ledger)
    if not entry["final"]:
        entry["final"] = "ESCALATE"
        print("ESCALATE - %d attempts without a verdict; a person decides" % len(entry["attempts"]))
    save_ledger(ledger_path, ledger)
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
