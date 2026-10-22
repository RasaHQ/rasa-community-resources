#!/usr/bin/env python3
"""Decide how much supervision the evidence supports, and refuse proposals that move the gate.

    python policy.py what-if  policy.json <passed> <total>        (arithmetic only; no data behind it)
    python policy.py proposal policy.json proposal.json

what-if: promotion needs the Wilson lower bound over the frozen set to reach the policy's bar AND no escaped
defects. One escaped defect demotes by a level, with no approval needed: tightening is always allowed.
proposal: a change that touches the gate's own files (acceptance, factory, tasks, this policy) cannot be approved
by the party that proposed it. It is refused here and goes to a person outside the proposal.
"""
import json
import sys
from pathlib import Path

from stats import wilson


def level(policy, i):
    return policy["levels"][max(0, min(i, len(policy["levels"]) - 1))]


def judge(policy, passed, total, escaped):
    lo = wilson(passed, total)[0]
    need = policy["promotion"]["min_wilson_lower_bound"]
    cur = policy["current"]
    print("evidence: %d of %d, Wilson lower bound %.3f (bar %.2f), escaped defects %d" % (passed, total, lo, need, escaped))
    if escaped > policy["promotion"]["max_escaped_defects"]:
        new = max(0, cur - 1)
        print("DEMOTE" if new < cur else "HOLD (already at the lowest level)", "->", level(policy, new))
        return 0
    if lo >= need and cur + 1 < len(policy["levels"]):
        print("ELIGIBLE for promotion ->", level(policy, cur + 1), "(a person still signs the policy change)")
        return 0
    print("HOLD at", level(policy, cur), "- the evidence does not support more" if lo < need else "- already at the top level")
    return 0


def what_if(policy_path, passed, total):
    print("WHAT-IF: hypothetical counts only; no experiment records were loaded.")
    return judge(json.loads(Path(policy_path).read_text()), int(passed), int(total), 0)


def proposal(policy_path, proposal_path):
    policy = json.loads(Path(policy_path).read_text())
    prop = json.loads(Path(proposal_path).read_text())
    touched = [f for f in prop["files"] if any(f.startswith(g) for g in policy["gate_paths"])]
    if touched:
        print("REFUSED - %s proposes to change the gate itself (%s); it needs a person who did not write the proposal" % (prop["proposed_by"], ", ".join(touched)))
        return 1
    print("OK - %s touches nothing the gate depends on" % prop["proposed_by"])
    return 0


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else (None, [])
    table = {"what-if": (what_if, 3), "proposal": (proposal, 2)}
    if cmd not in table or len(args) != table[cmd][1]:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(table[cmd][0](*args))
