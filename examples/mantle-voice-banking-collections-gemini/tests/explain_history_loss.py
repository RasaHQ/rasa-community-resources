#!/usr/bin/env python3
"""Compare retained and lost referral state using the real offline guard.

Losing state is an intentional fixture fault, not an observed Mantle failure.
Run from this example directory: python3 -B tests/explain_history_loss.py
"""
import json
import test_guard as t


def attempt(keep_referral):
    case = t.SelectAndRecordTests()
    case.setUp()
    # Stage normally, then simulate an obsolete staged offer surviving a referral.
    _, memory = case.stage("OFR-4471-3M")
    old_staged = dict(case.state.staged)
    referral = t.rp.request_hardship_referral(t.MARISOL, "4471", "Cannot afford rent",
                                            case.state, "t")
    assert referral["status"] == "referred"
    case.state.staged = old_staged
    if not keep_referral:
        case.state.referrals.clear()  # Deliberately discard the second source of evidence.
    # The visible history now contains only a plan request and its confirmation.
    result = case.record("OFR-4471-3M", memory)
    return {"status": result["status"], "effects": result["effects"],
            "reason": result.get("detail", result.get("reason"))}


def main():
    retained, lost = attempt(True), attempt(False)
    assert retained["status"] == "blocked" and retained["effects"] == 0
    assert retained["reason"] == "hardship_declared"
    assert lost["status"] == "succeeded" and lost["effects"] == 1
    print(json.dumps({"evidence_kind": "synthetic", "history_contains_hardship": False,
                      "referral_retained": retained, "referral_discarded": lost}, sort_keys=True))


if __name__ == "__main__":
    main()
