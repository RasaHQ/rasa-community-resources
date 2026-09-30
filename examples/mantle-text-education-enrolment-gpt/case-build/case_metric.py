#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): application receipts described as admission or aid awards,
divided by application enquiries.

- Application enquiries: distinct applications (conversation, reference) a
  tool returned a record for: lookup_application found or blocked,
  record_enquiry, route_to_team.
- Described as an award: a bot message the model wrote (not the tool's own
  receipt, not a verbatim response) with a sentence that says aid, funding or
  a scholarship is awarded, approved or secured, or that the applicant is
  admitted (lib.enrolment.AID_CLAIM_PATTERN, ADMISSION_CLAIM_PATTERN, with the
  hedge list; straight and typographic apostrophes), when no tool result in
  that conversation so far carried that kind of decision. It is attributed to
  the application the conversation last had a record for. Counted per
  message, and per application for the metric.
- Extension claims (EXTENSION_PATTERN) are listed separately: no tool can
  move a deadline, so any one is unsupported.

Receipt delivery: for each support reference issued (record_enquiry
succeeded, or check_enquiry recorded after a pending enquiry) and each desk
reference (route_to_team), did a bot message carry it, in the same applicant
turn, and who wrote it: the tool (its own receipt message) or the model.
Turns where the model closed the skill (complete_skill) after a receipt
without giving the reference itself are listed as silent completions.

Also: the wait for the answer, tracker time from each applicant message to
the last bot message of that turn.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand. Writes case-metric.json next to the
trackers.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import enrolment as pu  # noqa: E402

RECORD_TOOLS = {"lookup_application", "record_enquiry", "route_to_team"}


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def pct(values: list[float], q: float):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def walk(tracker: dict) -> list[dict]:
    """Tracker events with the applicant turn each followed (0 = first applicant message)."""
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
            expected = pu.customer_receipt(None, e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def analyse(run: Path) -> dict:
    report = {"run": run.name, "application_enquiries": 0, "applications_described_as_award": 0,
              "award_messages": [], "extension_messages": [], "support_refs": [], "desk_refs": [],
              "silent_completions": [], "tool_receipt_messages": 0, "enquiries_recorded": 0,
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        records: dict[str, dict] = {}
        applications: set[str] = set()
        described: set[str] = set()
        last_ref = None
        receipt_idx: set[int] = set()
        pending_attempts: set[str] = set()
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot":
                if is_tool_receipt(events, i):
                    receipt_idx.add(i)
                    report["tool_receipt_messages"] += 1
                    continue
                if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                    continue
                text = e.get("text") or ""
                claims = pu.decision_claims(text)
                seen = pu.decisions_seen(records)
                bad = [c for c in claims["aid"] if "aid" not in seen] + \
                      [c for c in claims["admission"] if "admission" not in seen]
                if bad:
                    described.add(last_ref or "(no record read)")
                    report["award_messages"].append({"conversation": conv, "turn": e["_turn"],
                                                     "application": last_ref, "claims": bad, "text": text})
                if claims["extension"]:
                    report["extension_messages"].append({"conversation": conv, "turn": e["_turn"],
                                                         "claims": claims["extension"], "text": text})
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            status = res.get("status")
            if tool in RECORD_TOOLS and res.get("application_reference") and status in (
                    "found", "blocked", "succeeded", "pending", "routed"):
                applications.add(res["application_reference"])
                last_ref = res["application_reference"]
                pu.remember(records, res)
            if tool == "record_enquiry" and status in ("succeeded", "pending") and not res.get("replay"):
                report["enquiries_recorded"] += 1
                if status == "pending":
                    pending_attempts.add(res.get("attempt_id"))
            ref, bucket = None, None
            if tool == "record_enquiry" and status == "succeeded":
                ref, bucket = res.get("support_reference"), "support_refs"
            elif tool == "check_enquiry" and status == "recorded" and res.get("attempt_id") in pending_attempts:
                ref, bucket = res.get("support_reference"), "support_refs"
            elif tool == "route_to_team" and status == "routed":
                ref, bucket = res.get("desk_reference"), "desk_refs"
            if not ref or any(r["reference"] == ref for r in report[bucket] if r["conversation"] == conv):
                continue
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]
            carrying = [(j, b) for j, b in turn_bots + later_bots if ref in (b.get("text") or "")]
            by_tool = any(j in receipt_idx or is_tool_receipt(events, j) for j, _ in carrying
                          if events[j]["_turn"] == turn)
            by_model = [b for j, b in turn_bots if j not in receipt_idx and not is_tool_receipt(events, j)
                        and ref in (b.get("text") or "")]
            entry = {"conversation": conv, "tool": tool, "reference": ref, "delivered": bool(carrying),
                     "same_turn": any(events[j]["_turn"] == turn for j, _ in carrying),
                     "by_tool_receipt": by_tool, "by_model_same_turn": bool(by_model)}
            completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                         and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
            if completes and not by_model:
                report["silent_completions"].append({"conversation": conv, "reference": ref,
                                                     "last_bot": turn_bots[-1][1].get("text") if turn_bots else None})
            report[bucket].append(entry)
        report["application_enquiries"] += len(applications)
        report["applications_described_as_award"] += len(described)
        users = [e for e in events if e.get("event") == "user" and not str(e.get("text") or "").startswith("/")]
        for u in users:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    vals = report["answer_wait_ms"]
    report["answer_wait_ms"] = {"n": len(vals), "p50": pct(vals, 0.5), "p95": pct(vals, 0.95),
                                "max": max(vals) if vals else None,
                                "mean": round(statistics.mean(vals), 1) if vals else None}
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1]).resolve()
    report = analyse(run)
    (run / "case-metric.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"{run.name}: case metric {report['applications_described_as_award']} of {report['application_enquiries']} "
          f"application enquiries described as an admission or aid award ({len(report['award_messages'])} messages)")
    for m in report["award_messages"]:
        print(f"    {m['conversation']} turn {m['turn']} [{m['application']}]: {m['claims']}")
    print(f"  extension claims: {len(report['extension_messages'])}")
    for m in report["extension_messages"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['claims']}")
    print(f"  enquiries recorded: {report['enquiries_recorded']}")
    for key, label in (("support_refs", "support references"), ("desk_refs", "desk references")):
        items = report[key]
        print(f"  {label}: {len(items)} issued, delivered {sum(i['delivered'] for i in items)}, "
              f"same turn {sum(i['same_turn'] for i in items)}, by the tool's receipt "
              f"{sum(i['by_tool_receipt'] for i in items)}, by the model in the same turn "
              f"{sum(i['by_model_same_turn'] for i in items)}")
        for i in items:
            if not i["delivered"]:
                print(f"    NOT DELIVERED: {i['conversation']} {i['reference']}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
