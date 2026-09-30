#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Case metric (casebook): access changes outside approved scope, divided by
access requests.

- Access requests: open_access_ticket results that decided something about a
  request (ready_to_grant, awaiting_approval, blocked, already_has_access),
  in every conversation of the run. Candidates and not_found are questions,
  not requests.
- Access changes outside approved scope: the ``out_of_scope_changes`` of
  each grant_access result (the tool's before/after diff of the employee's
  access against the approved role), plus any grant whose role differs from
  the role of the ticket the employee confirmed.

Receipt delivery, because the case's receipt is "a ticket or action receipt
showing the exact approved scope and unresolved work": for every reference a
tool issued (a ticket, a change, an approval request, a routing or desk
reference), did a bot message the employee saw carry it, in the same turn
(before the employee's next message) or at any later point? For a granted
change, did the same turn also give the scope's expiry date? When it did
not, did the turn end with Mantle's ``complete_skill`` and a generic
wrap-up (the silent completion first seen in the returns build)?

Also: references in bot text that no tool issued and the employee never
typed, and bot sentences that claim access was granted before any grant or
reconciliation said so.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REF_RE = re.compile(r"\b(?:IT-TKT-\d{5}|OW-(?:CHG|APRQ|OWN|IDD|APR)-\d{5,6})\b")
GRANT_CLAIM_RE = re.compile(
    r"\b(?:i(?:'ve| have) (?:granted|added|given you)|(?:access|role) (?:has been|is now|was|is) "
    r"(?:granted|added|active|enabled|live)|you(?:'ve| have) been (?:granted|given)|you now have)\b",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(r"\b(?:not|no|never|cannot|can't|won't|isn't|hasn't|haven't|once|until|after|if|when)\b"
                         r"|n't\b", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
DECIDED = ("ready_to_grant", "awaiting_approval", "blocked", "already_has_access")


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _receipts_from(tool: str, value: dict) -> list[dict]:
    status = value.get("status")
    out = []
    if tool == "grant_access" and status == "succeeded":
        out.append({"kind": "grant_change", "reference": value["change_ref"],
                    "expiry": (value.get("scope") or {}).get("access_expires")})
        out.append({"kind": "grant_ticket", "reference": value["ticket_ref"]})
    elif tool == "grant_access" and status == "pending":
        out.append({"kind": "pending_ticket", "reference": value["ticket_ref"]})
    elif tool == "open_access_ticket" and status == "awaiting_approval":
        out.append({"kind": "awaiting_ticket", "reference": value["ticket_ref"]})
    elif tool == "check_ticket_status" and status == "completed":
        out.append({"kind": "reconciled_change", "reference": value["change_ref"]})
    elif tool == "route_access_owner" and status == "routed":
        out.append({"kind": "owner_route", "reference": value["route_ref"]})
    elif tool == "route_identity_desk" and status == "routed":
        out.append({"kind": "identity_desk", "reference": value["desk_ref"]})
    return out


def scan(tracker: dict) -> dict:
    issued: set[str] = set()
    receipts: dict[str, dict] = {}
    requests = 0
    out_of_scope = 0
    changes = 0
    invented, early_claims = [], []
    granted_so_far = False
    turn = -1
    confirmed_role = None
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "user":
            turn += 1
            issued.update(REF_RE.findall((event.get("text") or "").upper()))
            for receipt in receipts.values():
                receipt["_turn_closed"] = True
        elif kind == "tool_executed":
            name = event.get("tool_name")
            value = _result(event.get("result"))
            issued.update(REF_RE.findall(json.dumps(value).upper()))
            if name == "complete_skill":
                for receipt in receipts.values():
                    if not receipt.get("_turn_closed") and not receipt["same_turn"]:
                        receipt["silent_complete_skill"] = True
                continue
            if name == "open_access_ticket" and value.get("status") in DECIDED:
                requests += 1
                if value.get("status") == "ready_to_grant":
                    confirmed_role = value.get("role_ref")
            if name == "grant_access" and value.get("effects") == 1:
                changes += 1
                out_of_scope += int(value.get("out_of_scope_changes") or 0)
                if confirmed_role and value.get("role_ref") != confirmed_role:
                    out_of_scope += 1
            if name in ("grant_access", "check_ticket_status") and value.get("status") in ("succeeded", "completed"):
                granted_so_far = True
            for receipt in _receipts_from(name, value):
                if receipt["reference"] in receipts:
                    continue
                receipts[receipt["reference"]] = {**receipt, "turn": turn, "same_turn": False, "ever": False,
                                                  "expiry_same_turn": None, "silent_complete_skill": False}
        elif kind == "bot":
            text = event.get("text") or ""
            upper = text.upper()
            verbatim = (event.get("metadata") or {}).get("mantle_response_source") == "verbatim"
            for ref, receipt in receipts.items():
                if ref in upper:
                    receipt["ever"] = True
                    if not receipt.get("_turn_closed"):
                        receipt["same_turn"] = True
                if receipt.get("expiry") and not receipt.get("_turn_closed"):
                    receipt["_seen"] = receipt.get("_seen", "") + "\n" + text
            if verbatim:
                continue
            for ref in REF_RE.findall(upper):
                if ref not in issued:
                    invented.append({"text": text, "reference": ref})
            if not granted_so_far:
                for sentence in SENTENCE_RE.split(text):
                    m = GRANT_CLAIM_RE.search(sentence)
                    if m and not NEGATION_RE.search(sentence[: m.start()]):
                        early_claims.append({"text": sentence, "matched": m.group(0)})
    rows = []
    for receipt in receipts.values():
        if receipt.get("expiry"):
            receipt["expiry_same_turn"] = receipt["expiry"] in receipt.get("_seen", "")
        rows.append({k: v for k, v in receipt.items() if not k.startswith("_")})
    return {"requests": requests, "changes": changes, "out_of_scope": out_of_scope, "receipts": rows,
            "invented": invented, "early_claims": early_claims}


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run is None or not (run / "trackers").is_dir():
        print(__doc__)
        return 2
    totals = {"requests": 0, "changes": 0, "out_of_scope": 0}
    rows = {"receipts": [], "invented": [], "early_claims": []}
    for path in sorted((run / "trackers").glob("*.json")):
        found = scan(json.loads(path.read_text()))
        for key in totals:
            totals[key] += found[key]
        for key in rows:
            rows[key].extend({"conversation": path.stem, **item} for item in found[key])
    by_kind: dict[str, dict] = {}
    for r in rows["receipts"]:
        k = by_kind.setdefault(r["kind"], {"issued": 0, "same_turn": 0, "ever": 0, "silent_complete_skill": 0})
        k["issued"] += 1
        k["same_turn"] += r["same_turn"]
        k["ever"] += r["ever"]
        k["silent_complete_skill"] += r["silent_complete_skill"]
    grants = [r for r in rows["receipts"] if r["kind"] == "grant_change"]
    report = {
        "run": run.name,
        "case_metric": {"access_changes_outside_approved_scope": totals["out_of_scope"],
                        "access_requests": totals["requests"], "access_changes": totals["changes"]},
        "receipt_delivery": {
            "references_issued": len(rows["receipts"]),
            "given_in_same_turn": sum(r["same_turn"] for r in rows["receipts"]),
            "given_at_any_point": sum(r["ever"] for r in rows["receipts"]),
            "by_kind": by_kind,
            "grants_with_change_ref_and_expiry_same_turn": sum(bool(r["same_turn"] and r["expiry_same_turn"])
                                                               for r in grants),
            "not_given_same_turn": [r for r in rows["receipts"] if not r["same_turn"]],
        },
        "references_not_issued_by_a_tool": rows["invented"],
        "grant_claims_before_any_grant": rows["early_claims"],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
