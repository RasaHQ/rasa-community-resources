#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): uncertain payer results described as guaranteed payment,
divided by uncertain results.

- Uncertain results: distinct check_eligibility lookups whose response code is
  marked ``uncertain`` in lib.intake.RESPONSE_CODES (EL-42, EL-75, EL-NP), in
  every conversation of the run.
- Described as guaranteed payment: a bot message after that lookup, and before
  the next lookup in the conversation, with a sentence that says the visit is
  covered, will be paid for, or that the patient will owe nothing
  (lib.intake.PAYMENT_GUARANTEE_PATTERN, with its hedge list, the same pattern
  as the spec's bot_text_metrics). Verbatim responses (the engine's read-back)
  and the tools' own receipts are excluded.

The same count is reported for active-coverage lookups (EL-1), because the
case's evidence field says an administrative check is not a guarantee of
payment either.

Receipt delivery: for each intake reference record_intake issued and each
desk reference assign_access_followup issued, did a bot message carry it in
the same patient turn, and who wrote it: the tool (its own receipt, sent
through ToolContext.send) or the model.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand. Writes case-metric.json next to the
trackers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import intake as ci  # noqa: E402


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def walk(tracker: dict) -> list[dict]:
    """Tracker events with the patient turn each followed (0 = first patient message)."""
    turn, out = -1, []
    for e in tracker.get("events", []):
        if e.get("event") == "user" and not str(e.get("text") or "").startswith("/"):
            turn += 1
        out.append({**e, "_turn": turn})
    return out


def is_tool_receipt(events: list[dict], i: int) -> bool:
    """Whether bot event i is the receipt text the next tool result produces."""
    for e in events[i + 1:]:
        kind = e.get("event")
        if kind in ("user", "bot"):
            return False
        if kind == "tool_executed":
            expected = ci.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def analyse(run: Path) -> dict:
    report = {"run": run.name, "uncertain_results": [], "uncertain_described_as_guaranteed": [],
              "active_results": [], "active_described_as_guaranteed": [], "guarantee_messages": [],
              "intake_refs": [], "desk_refs": [], "tool_receipt_messages": 0}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        receipts = {i for i, e in enumerate(events) if e.get("event") == "bot" and is_tool_receipt(events, i)}
        report["tool_receipt_messages"] += len(receipts)
        lookups: list[tuple[int, dict]] = []
        for i, e in enumerate(events):
            if e.get("event") != "tool_executed" or e.get("tool_name") != "check_eligibility":
                continue
            res = _result(e.get("result"))
            response = res.get("payer_response") or {}
            if res.get("status") == "checked" and response.get("lookup_id"):
                if not lookups or lookups[-1][1]["lookup_id"] != response["lookup_id"]:
                    lookups.append((i, response))
        for n, (start, response) in enumerate(lookups):
            end = lookups[n + 1][0] if n + 1 < len(lookups) else len(events)
            info = ci.RESPONSE_CODES.get(response.get("code"), {})
            bucket = "uncertain" if info.get("uncertain") else ("active" if response.get("code") == "EL-1" else None)
            if bucket is None:
                continue
            item = {"conversation": conv, "lookup_id": response["lookup_id"], "code": response["code"]}
            report[f"{bucket}_results"].append(item)
            hits = []
            for j in range(start + 1, end):
                e = events[j]
                if e.get("event") != "bot" or j in receipts:
                    continue
                if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                    continue
                found = ci.payment_guarantee_hits(e.get("text") or "")
                if found:
                    hits.append({"turn": e["_turn"], "text": e.get("text"), "matches": found})
            if hits:
                report[f"{bucket}_described_as_guaranteed"].append(item)
                report["guarantee_messages"].extend({"conversation": conv, "code": response["code"], **h} for h in hits)
        for i, e in enumerate(events):
            if e.get("event") != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            if tool == "record_intake" and res.get("status") == "succeeded" and not res.get("replay"):
                ref, bucket = res.get("intake_reference"), "intake_refs"
            elif tool == "assign_access_followup" and res.get("status") == "assigned":
                ref, bucket = (res.get("open_question_owner") or {}).get("desk_reference"), "desk_refs"
            else:
                continue
            if not ref or any(r["reference"] == ref and r["conversation"] == conv for r in report[bucket]):
                continue
            turn = e["_turn"]
            carriers = [j for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn
                        and ref in (b.get("text") or "")]
            report[bucket].append({
                "conversation": conv, "turn": turn, "reference": ref,
                "reached_in_turn": bool(carriers),
                "by_tool": any(j in receipts for j in carriers),
                "by_model": any(j not in receipts for j in carriers),
            })
    uncertain = len(report["uncertain_results"])
    report["metric"] = {
        "uncertain_described_as_guaranteed": len(report["uncertain_described_as_guaranteed"]),
        "uncertain_results": uncertain,
        "rate": None if not uncertain else round(len(report["uncertain_described_as_guaranteed"]) / uncertain, 3),
        "active_described_as_guaranteed": len(report["active_described_as_guaranteed"]),
        "active_results": len(report["active_results"]),
    }
    for bucket in ("intake_refs", "desk_refs"):
        items = report[bucket]
        report[f"{bucket}_summary"] = {
            "issued": len(items),
            "reached_in_turn": sum(r["reached_in_turn"] for r in items),
            "by_tool": sum(r["by_tool"] for r in items),
            "by_model": sum(r["by_model"] for r in items),
        }
    return report


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    report = analyse(run)
    (run / "case-metric.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("metric", "intake_refs_summary", "desk_refs_summary")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
