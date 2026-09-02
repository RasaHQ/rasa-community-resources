#!/usr/bin/env python3
"""The fixture agent desk, as a runnable screen.

    python scripts/agent_desk.py            # the demo handoff, end to end
    python scripts/agent_desk.py --compare  # against what the catalog ships today
    python scripts/agent_desk.py <file>     # a package delivered by the agent

The comparison mode is the one worth running first. It builds two packages from
the SAME session state — one through this pattern's contract, one carrying only
the free-text `handoff_reason` that every existing example transfers — and shows
both desk screens side by side. The difference is not a matter of taste; it is
the list of questions the caller is about to be asked again.

No network, no credentials, no model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handoffpkg.desk import (  # noqa: E402
    DESK_OPENING_SCRIPT,
    reconstruct,
    unanswered_questions,
)
from handoffpkg.redaction import build_package_from_session  # noqa: E402
from handoffpkg.schema import package_from_dict  # noqa: E402

# The same session used by the eval suite: real business state next to real
# credentials, because that is what a live session actually contains.
DEMO_SESSION = {
    "customer_id": "cust_00417",
    "display_name": "Jordan Rivera",
    "verified_tier": "medium",
    "verified_factors": ["knowledge_passphrase"],
    "channel": "voice:+1-555-0100",
    "goal": "dispute_transaction",
    "goal_label": "Dispute a card transaction",
    "goal_stage": "blocked",
    "account_id": "acc_checking",
    "account_label": "Everyday Checking",
    "card_last_four": "4821",
    "dispute_amount": "$248.00",
    "dispute_merchant": "Northgate Fuel",
    "dispute_date": "2026-08-29",
    "handoff_reason": "Dispute needs a second factor the caller cannot complete on this line.",
    "attempts": [
        {"action": "verify_passphrase", "outcome": "succeeded",
         "detail": "Caller answered the knowledge factor on the first try."},
        {"action": "send_otp_sms", "outcome": "failed", "code": "delivery_failed",
         "detail": "Carrier rejected the SMS twice. Do not resend to this number."},
        {"action": "raise_dispute", "outcome": "blocked", "code": "insufficient_tier",
         "detail": "Dispute needs tier 'high'; caller is at 'medium'."},
    ],
    "questions_answered": [
        "Can I take your name?",
        "Can you confirm your date of birth?",
        "Which account is this about?",
        "What are you calling about today?",
        "Have you tried anything already?",
    ],
    "factors_verified": ["knowledge_passphrase"],
    "confirmed_facts": ["Caller consented to the call being recorded."],
    # Present in the session and must not cross. Same values the eval suite plants.
    "pin_attempt": "4242",
    "otp_code": "889134",
    "card_number": "4111111111111111",
    "auth_token": "tok_live_51H8xQe",
    "recording_url": "https://recordings.internal/call/9931.wav",
}


def _report(package, title: str) -> None:
    print()
    print(f"### {title}")
    print()
    print(reconstruct(package).render())
    outstanding = unanswered_questions(package)
    print()
    if outstanding:
        print(f"The caller will now be asked {len(outstanding)} question(s) they already answered:")
        for question in outstanding:
            print(f"  ✗ {question}")
    else:
        print(f"All {len(DESK_OPENING_SCRIPT)} opening questions are answered. The desk asks none of them.")


def main() -> int:
    args = sys.argv[1:]

    if args and args[0] not in ("--compare", "-c"):
        path = Path(args[0])
        if not path.is_file():
            print(f"No such package: {path}", file=sys.stderr)
            return 1
        package = package_from_dict(json.loads(path.read_text(encoding="utf-8")))
        _report(package, f"Delivered package {path.name}")
        return 0

    package = build_package_from_session(DEMO_SESSION, handoff_id="ho_demo01")

    if args and args[0] in ("--compare", "-c"):
        # What the catalog transfers today: one free-text reason. Built from the
        # SAME session, so the difference is the contract and nothing else.
        today = build_package_from_session(
            {"handoff_reason": DEMO_SESSION["handoff_reason"]},
            handoff_id="ho_today",
        )
        _report(today, "TODAY — one free-text handoff_reason (every example in the catalog)")
        _report(package, "THIS PATTERN — a structured context package")
        return 0

    _report(package, "Agent desk — inbound handoff")
    print()
    print("Withheld by policy (names crossed, values did not):")
    for name in package.withheld_fields:
        print(f"  · {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
