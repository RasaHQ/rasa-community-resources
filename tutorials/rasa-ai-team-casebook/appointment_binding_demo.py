#!/usr/bin/env python3
"""Expose the boolean lab's limits. Synthetic, stdlib-only; no booking service."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import casebook


def main():
    spec = casebook.load_case("banking-advisor-appointment")
    phone = {"channel": "phone", "slot": "Tuesday 10:00", "purpose": "online banking"}
    branch = {"channel": "branch", "slot": "Wednesday 11:30", "purpose": "online banking"}
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "lab.sqlite"
        first = casebook.execute(spec, spec["facts"], "appointment-1", database)
        changed = deepcopy(spec)
        changed["question"] = "Would you like Wednesday at the step-free branch?"
        replay = casebook.execute(changed, changed["facts"], "appointment-1", database)
        explicit = casebook.execute(spec, dict(spec["facts"], channel="branch"), "appointment-2", database)
        assert first["status"] == replay["status"] == "succeeded"
        assert replay["replay"] and replay["reference"] == first["reference"]
        assert casebook.contract_hash(spec) == casebook.contract_hash(changed)
        assert explicit["reason"] == "unknown_fact"
        assert casebook.digest(phone) != casebook.digest(branch)
        assert casebook.count_effects(database) == 1
        print(json.dumps({"evidence_kind": "synthetic", "same_boolean_facts": True,
                          "changed_question_replays": replay["replay"],
                          "explicit_channel_reason": explicit["reason"],
                          "appointment_payloads_differ": True, "stored_lab_actions": 1}, sort_keys=True))


if __name__ == "__main__":
    main()
