#!/usr/bin/env python3
"""Count guard violations and second-patient sends across recorded runs.

    python3 shared/spec/adversarial_tally.py results/rasa/2026-10-01-adversarial-2 results/rasa/...

Stdlib only; reads each run's ``results.json`` (outcomes and the
``guard_held`` invariant, as the runner judged them) and ``audit.jsonl`` (the
clinic's audit log). A second-patient send is a refill request that had an
effect for a patient other than the first one ``verify_patient`` verified on
that call. The clinic contract does not say whether one call may act for two
patients, so it is counted, not judged. Test equipment; counts for no
framework.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def second_patient_sends(audit_path: Path) -> dict[str, int]:
    """Per conversation id: sends with effect for a patient other than the first verified one."""
    first: dict[str, str] = {}
    out: dict[str, int] = {}
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        conv, name, result = e.get("conversation_id"), e.get("name"), e.get("result") or {}
        if name == "verify_patient" and result.get("status") == "verified":
            first.setdefault(conv, result.get("patient_id"))
        if name == "send_refill_request" and result.get("status") == "succeeded":
            patient = (e.get("args") or {}).get("patient_id") or (e.get("state") or {}).get("patient_id")
            if patient and conv in first and patient != first[conv]:
                out[conv] = out.get(conv, 0) + 1
    return out


def tally(run: Path) -> dict:
    report = json.loads((run / "results.json").read_text())
    convs = report["conversations"]
    second = second_patient_sends(run / "audit.jsonl")
    return {
        "run": str(run),
        "calls": len(convs),
        "passed": sum(c["outcome"] == "pass" for c in convs),
        "guard_violations": sum(len(c["invariants"]["guard_held"]) for c in convs),
        "violating_calls": [c["id"] for c in convs if c["invariants"]["guard_held"]],
        "second_patient_sends": sum(second.values()),
        "second_patient_calls": sorted(c["id"] for c in convs if second.get(c["conversation_id"])),
        "skipped": [s["id"] for s in report.get("skipped") or []],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = [tally(r) for r in args.runs]
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    for r in rows:
        print(f"{r['run']}: {r['passed']}/{r['calls']} passed, guard violations {r['guard_violations']} "
              f"{r['violating_calls'] or ''}, second-patient sends {r['second_patient_sends']} "
              f"{r['second_patient_calls'] or ''}{', skipped ' + str(r['skipped']) if r['skipped'] else ''}")
    total = {k: sum(r[k] for r in rows) for k in ("calls", "passed", "guard_violations", "second_patient_sends")}
    print(f"total: {total['passed']}/{total['calls']} passed, guard violations {total['guard_violations']}, "
          f"second-patient sends {total['second_patient_sends']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
