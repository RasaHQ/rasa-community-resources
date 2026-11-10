#!/usr/bin/env python3
"""Measure a Mantle factory over a folder of runs, and say what was not recorded.

    python measure.py report <runs-dir> [<runs-dir> ...]
    python measure.py intervals <n>          both intervals for every possible count of passes out of n
    python measure.py needed <bar> [fails]   smallest n whose Wilson lower bound reaches <bar>, with <fails> failures

report reads every <runs-dir>/<run>/decision.json the factory wrote. A person may add <run>/meta.json with
{"agent": "...", "seconds": 0, "human_interventions": 0, "cost_usd": 0.0}. Whatever is missing is listed as not
recorded. It is never estimated.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from stats import smallest_n_for_lower_bound, wald, wilson

FIELDS = ("agent", "seconds", "human_interventions", "cost_usd")


def report(*runs_dirs):
    runs = []
    for runs_dir in runs_dirs:
        for folder in sorted(p for p in Path(runs_dir).iterdir() if (p / "decision.json").exists()):
            decision = json.loads((folder / "decision.json").read_text())
            meta = json.loads((folder / "meta.json").read_text()) if (folder / "meta.json").exists() else {}
            runs.append((folder.name, decision, meta))
    if not runs:
        print("no decision.json files under", ", ".join(runs_dirs))
        return 1
    n = len(runs)
    accepted = sum(d["decision"] == "ACCEPT" for _, d, _ in runs)
    fmt = lambda iv: "%.2f to %.2f" % iv
    print("%d runs, rasa-pro %s" % (n, ", ".join(sorted({d["rasa_pro"] for _, d, _ in runs}))))
    print("accepted: %d of %d = %.2f" % (accepted, n, accepted / n))
    print("  Wald 95%%:   %s" % fmt(wald(accepted, n)))
    print("  Wilson 95%%: %s" % fmt(wilson(accepted, n)))
    per_task = defaultdict(Counter)
    for _, d, _ in runs:
        per_task[d["task"]][d["decision"]] += 1
    for task, counts in sorted(per_task.items()):
        print("  %-18s %d accepted, %d rejected" % (task, counts["ACCEPT"], counts["REJECT"]))
    per_agent = defaultdict(Counter)
    for _, d, m in runs:
        if "agent" in m:
            per_agent[m["agent"]][d["decision"]] += 1
    for agent, counts in sorted(per_agent.items()):
        print("  %-24s %d accepted, %d rejected" % (agent, counts["ACCEPT"], counts["REJECT"]))
    silent = [name for name, d, _ in runs if d["decision"] == "REJECT" and any(c["name"].startswith("builder") and c["passed"] for c in d["checks"])]
    print("rejected although the builder's own tests passed: %d %s" % (len(silent), silent))
    seconds = [m["seconds"] for _, _, m in runs if "seconds" in m]
    if seconds:
        print("seconds per run: median %s, range %s to %s (%d of %d recorded)" % (median(seconds), min(seconds), max(seconds), len(seconds), n))
    missing = [f for f in FIELDS if any(f not in m for _, _, m in runs)]
    print("not fully recorded, so not reported: %s" % (", ".join(missing) if missing else "nothing"))
    return 0


def intervals(n):
    n = int(n)
    print("passes of %d   Wald 95%%        Wilson 95%%" % n)
    for k in range(n + 1):
        print("%6d        %.2f to %.2f    %.2f to %.2f" % ((k,) + wald(k, n) + wilson(k, n)))
    return 0


def needed(bar, fails=0):
    n = smallest_n_for_lower_bound(float(bar), int(fails))
    print("%d runs, %s of them failing, put the Wilson lower bound at or above %s" % (n, fails, bar))
    return 0


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else (None, [])
    table = {"report": report, "intervals": intervals, "needed": needed}
    if cmd not in table or (cmd in ("intervals",) and len(args) != 1) or (cmd == "report" and len(args) < 1) or (cmd == "needed" and len(args) not in (1, 2)):
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(table[cmd](*args))
