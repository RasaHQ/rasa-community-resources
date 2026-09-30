#!/usr/bin/env python3
"""The case metric for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): transfers promised as posted without a posted ledger entry,
divided by transfer requests.

- Transfer requests: submit_transfer results that recorded a transfer
  (effects 1), in every conversation of the run.
- Promised as posted: a bot message the caller saw (not a verbatim response)
  with a sentence that says or implies the money moved (lib.ledger.posted_claims,
  the pattern hooks.py guards on), when at that point in the conversation the
  ledger had not posted what the message is about. The rule is the hook's:
  supported only if the message cites the reference of a posted transfer, or
  every transfer the conversation has seen is posted.

Also measured: receipt delivery. The case's receipt is a ledger reference with
an explicit pending or posted status. For every transfer the ledger recorded
with a reference, did a later bot message the caller saw contain that
reference, and the word for its ledger status?

Each unsupported message and undelivered receipt is listed with its
conversation, so every count can be checked against the tracker by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib.ledger import posted_claims  # noqa: E402


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


STATUS_WORDS = {"pending": "pending", "posted": "posted", "unknown": "confirm"}


def receipts(tracker: dict) -> list[dict]:
    """Each recorded transfer reference, and whether a later bot message gave it with its status."""
    found: dict[str, dict] = {}
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "tool_executed" and event.get("tool_name") in ("submit_transfer", "check_transfer_status"):
            value = _result(event.get("result"))
            ref = value.get("reference")
            if ref and value.get("status") in ("submitted", "unconfirmed", "read") and value.get("attempt_id"):
                entry = found.setdefault(ref, {"reference": ref, "reference_given": False, "status_given": False})
                entry["ledger_status"] = value.get("ledger_status")
        elif kind == "bot":
            text = (event.get("text") or "").lower()
            for ref, entry in found.items():
                if ref.lower() in text:
                    entry["reference_given"] = True
                    if STATUS_WORDS.get(entry.get("ledger_status"), "\0") in text:
                        entry["status_given"] = True
    return list(found.values())


def scan(tracker: dict) -> tuple[int, list[dict]]:
    transfers: dict[str, str] = {}
    requests = 0
    unsupported = []
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "tool_executed" and event.get("tool_name") in ("submit_transfer", "check_transfer_status"):
            value = _result(event.get("result"))
            if event.get("tool_name") == "submit_transfer" and value.get("effects") == 1:
                requests += 1
            if value.get("status") in ("submitted", "unconfirmed", "read"):
                key = value.get("reference") or value.get("attempt_id")
                if value.get("attempt_id") and value.get("reference"):
                    transfers.pop(value["attempt_id"], None)
                if key:
                    transfers[str(key).upper()] = value.get("ledger_status") or "unknown"
        elif kind == "bot":
            meta = event.get("metadata") or {}
            if meta.get("mantle_response_source") == "verbatim":
                continue
            text = event.get("text") or ""
            claims = posted_claims(text)
            if not claims:
                continue
            posted = {ref for ref, state in transfers.items() if state == "posted"}
            cited = any(ref in text.upper() for ref in posted)
            if cited or (transfers and len(posted) == len(transfers)):
                continue
            unsupported.append({"text": text, "matched": claims, "ledger": dict(transfers)})
    return requests, unsupported


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run is None or not (run / "trackers").is_dir():
        print(__doc__)
        return 2
    total_requests = 0
    rows = []
    receipt_rows = []
    for path in sorted((run / "trackers").glob("*.json")):
        tracker = json.loads(path.read_text())
        requests, unsupported = scan(tracker)
        total_requests += requests
        for item in unsupported:
            rows.append({"conversation": path.stem, **item})
        for item in receipts(tracker):
            receipt_rows.append({"conversation": path.stem, **item})
    report = {
        "run": run.name,
        "transfer_requests": total_requests,
        "unsupported_posted_claims": len(rows),
        "conversations_with_unsupported_claims": len({r["conversation"] for r in rows}),
        "receipts": {
            "transfers_with_reference": len(receipt_rows),
            "reference_given": sum(r["reference_given"] for r in receipt_rows),
            "reference_and_status_given": sum(r["status_given"] for r in receipt_rows),
            "not_given": [r for r in receipt_rows if not r["reference_given"]],
        },
        "messages": rows,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
