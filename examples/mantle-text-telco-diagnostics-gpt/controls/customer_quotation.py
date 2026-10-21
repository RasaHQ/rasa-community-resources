"""Expose a known selection failure when a customer quotes reset advice.

Constructed service inputs only: no Strands/model/Mantle/real-device call.
The default run deliberately exits one while this known contract failure exists.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import juniper as jm  # noqa: E402

SHOP = "JM-FB-204988"
CASES = {
    "quotation": 'The specialist said "factory reset". What does that mean?',
    "negation": "Please do not factory reset my shop hub.",
    "request": "I want a factory reset of my shop hub.",
}


def run_cases() -> dict:
    """Use a fresh service for each case, with only its customer-owned turn."""
    cases = {}
    for name, words in CASES.items():
        net = jm.NetworkService()
        jm.check_area_outage(net, jm.DEMO_CUSTOMER_ID, SHOP)
        result = jm.select_recovery_step(
            net, jm.DEMO_CUSTOMER_ID, SHOP, "factory_reset", [words]
        )
        cases[name] = {
            "customer_words": words,
            "result": result,
            "selection": net.selection,
            "commands": list(net.command_log),
        }
    return {"scope": "Constructed customer-only service inputs; no model, Strands or Mantle execution", "cases": cases}


def require_request_boundary(record: dict) -> None:
    """The proposed user-facing contract, explicitly separate from current behavior.

    Use explicit raises so optimised Python cannot erase the evidence check.
    This is a regression detector, not a repaired language/intent classifier.
    """
    cases = record["cases"]
    for name in ("quotation", "negation"):
        case = cases[name]
        if case["result"]["status"] != "blocked" or case["selection"] is not None:
            raise AssertionError(f"{name}: mentioning a reset is not a request to select it")
        if case["commands"]:
            raise AssertionError(f"{name}: a non-request must send no command")
    positive = cases["request"]
    if positive["result"]["status"] != "selected" or positive["selection"] is None:
        raise AssertionError("request: explicit choice must still select the operation")
    if positive["commands"]:
        raise AssertionError("Selection alone must send no command")


def main() -> int:
    record = run_cases()
    print(json.dumps(record, indent=2, sort_keys=True))
    try:
        require_request_boundary(record)
    except AssertionError as error:
        print(f"KNOWN_CONTRACT_FAILURE: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
