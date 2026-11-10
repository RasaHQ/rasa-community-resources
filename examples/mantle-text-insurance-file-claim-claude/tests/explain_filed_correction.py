#!/usr/bin/env python3
"""A confirmed draft correction and a filed-report correction differ.

Run from this example directory: python3 -B tests/explain_filed_correction.py
No model or claims service is contacted.
"""
import json
import test_guard as t


def main():
    messages = t.SubmissionTests.MSGS
    service = t.hc.ClaimsIntake()
    draft = t.drafted(service, messages)
    first = t.hc.submit_claim_report(service, t.ME, t.hc.memory_values(service, draft),
                                    t.confirmed(service, draft, messages), draft.draft_id)
    update, _ = t.hc.update_claim_draft(service, t.ME, t.convo(*messages), draft.draft_id,
                                       loss_date="2026-09-25")
    again = t.hc.submit_claim_report(service, t.ME, t.hc.memory_values(service, draft),
                                    t.confirmed(service, draft, messages), draft.draft_id)
    assert first["status"] == "succeeded"
    assert update["status"] == "blocked" and update["reason"] == "already_submitted"
    assert again["replay"] and again["effects"] == 0
    assert again["loss_date"] == first["loss_date"] == "2026-09-26"
    assert again["claim_intake_reference"] == first["claim_intake_reference"]
    assert len(service.submissions) == 1
    print(json.dumps({"evidence_kind": "synthetic", "correction_reason": update["reason"],
                      "replayed_loss_date": again["loss_date"], "additional_filings": again["effects"],
                      "same_reference": True}, sort_keys=True))


if __name__ == "__main__":
    main()
