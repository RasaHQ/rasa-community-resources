#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): drafts described as filed without acknowledgment, divided
by filing attempts.

- Filing attempts: submit_claim_report calls that reached the tool (the result
  is succeeded, pending or blocked; the engine's awaiting_confirmation and
  declined payloads are not attempts), in every conversation of the run.
- Described as filed without acknowledgment: a bot message with a sentence
  that says a claim is filed (lib.claims.FILED_CLAIM_PATTERN, with its hedge
  list) when no tool had acknowledged a claim in that conversation by then.
  The tool's own receipt (TOOL_SENDS_RECEIPT) is recorded just before its
  tool_executed event, so a message that is exactly the receipt the next tool
  result produces counts as acknowledged. Counted per message and per draft.

Receipt delivery, the question this build was asked: for each claim-intake
reference a tool issued (submit_claim_report succeeded, or
check_claim_submission acknowledged after a pending submission), did a bot
message carry that reference, in the same customer turn, and who wrote it:
the tool (its own receipt message) or the model. The same for each desk
reference from route_claims_intake. For a receipt with material still
needed, did the model's own text in that turn name it. Turns where the model
closed the skill (complete_skill) after a receipt without giving the
reference itself are listed as silent completions.

Also: the wait for the answer, tracker time from each customer message to the
last bot message of that turn.

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

from lib import claims as hc  # noqa: E402

FILED = re.compile(hc.FILED_CLAIM_PATTERN, re.IGNORECASE)
HEDGE = re.compile(hc.FILED_HEDGE_PATTERN, re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
ACK = {("submit_claim_report", "succeeded"), ("check_claim_submission", "acknowledged")}


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def filed_sentences(text: str) -> list[str]:
    hits = []
    for sentence in SENTENCE.split(text or ""):
        for m in FILED.finditer(sentence):
            if not HEDGE.search(sentence[: m.start()]):
                hits.append(sentence.strip())
                break
    return hits


def pct(values: list[float], q: float):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def walk(tracker: dict) -> list[dict]:
    """Tracker events with the customer turn each followed (0 = first customer message)."""
    turn, out = -1, []
    for e in tracker.get("events", []):
        if e.get("event") == "user" and not str(e.get("text") or "").startswith("/"):
            turn += 1
        out.append({**e, "_turn": turn})
    return out


def is_tool_receipt(events: list[dict], i: int) -> tuple[bool, dict | None]:
    """Whether bot event i is the receipt text the next tool result produces, and that tool call."""
    for e in events[i + 1:]:
        kind = e.get("event")
        if kind in ("user", "bot"):
            return False, None
        if kind == "tool_executed":
            res = _result(e.get("result"))
            expected = hc.customer_receipt(e.get("tool_name"), res)
            return expected is not None and expected == events[i].get("text"), e
    return False, None


def analyse(run: Path) -> dict:
    report = {"run": run.name, "filing_attempts": 0, "filed_without_ack_messages": [], "drafts_described_filed_without_ack": 0,
              "claim_refs": [], "desk_refs": [], "silent_completions": [], "answer_wait_ms": [],
              "tool_receipt_messages": 0}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        acked = False
        bad_drafts: set[str] = set()
        tool_receipt_idx: set[int] = set()
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot":
                own, _ = is_tool_receipt(events, i)
                if own:
                    tool_receipt_idx.add(i)
                    report["tool_receipt_messages"] += 1
                meta = e.get("metadata") or {}
                if meta.get("mantle_response_source") == "verbatim":
                    continue
                hits = filed_sentences(e.get("text") or "")
                if hits and not acked and not own:
                    draft = next((d for d in re.findall(r"HC-FD-[A-Z0-9]{5}", json.dumps(
                        [x.get("result") for x in events[:i] if x.get("event") == "tool_executed"]))[-1:]), conv)
                    bad_drafts.add(draft)
                    report["filed_without_ack_messages"].append({"conversation": conv, "turn": e["_turn"],
                                                                 "sentences": hits})
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            status = res.get("status")
            if tool == "submit_claim_report" and status in ("succeeded", "pending", "blocked") and not res.get("replay"):
                report["filing_attempts"] += 1
            if (tool, status) in ACK or (tool == "check_claim_submission" and status == "filed"):
                acked = True
            ref, bucket = None, None
            if (tool, status) in ACK and not res.get("replay", False) or (
                    tool == "check_claim_submission" and status == "acknowledged"):
                ref, bucket = res.get("claim_intake_reference"), "claim_refs"
            elif tool == "route_claims_intake" and status == "routed":
                ref, bucket = res.get("desk_reference"), "desk_refs"
            if not ref or any(r["reference"] == ref for r in report[bucket] if r["conversation"] == conv):
                continue
            turn = e["_turn"]
            # Bot messages from the customer turn this tool ran in, before and after it
            # (the tool's own receipt is recorded just before its event).
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]
            carrying = [(j, b) for j, b in turn_bots + later_bots if ref in (b.get("text") or "")]
            by_tool = any(j in tool_receipt_idx for j, _ in carrying if events[j]["_turn"] == turn)
            by_model_same_turn = [b for j, b in turn_bots if j not in tool_receipt_idx and ref in (b.get("text") or "")]
            entry = {"conversation": conv, "tool": tool, "reference": ref,
                     "delivered": bool(carrying),
                     "same_turn": any(events[j]["_turn"] == turn for j, _ in carrying),
                     "by_tool_receipt": by_tool,
                     "by_model_same_turn": bool(by_model_same_turn)}
            if bucket == "claim_refs":
                follow = [f["requirement"] for f in res.get("follow_up_required") or []]
                model_text = " ".join(b.get("text") or "" for j, b in turn_bots if j not in tool_receipt_idx and j > i)
                entry["follow_up"] = follow
                entry["model_named_follow_up"] = all(f.split(" ")[0] in model_text.lower() for f in follow) if follow else None
                completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                             and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
                if completes and not by_model_same_turn:
                    report["silent_completions"].append({"conversation": conv, "reference": ref,
                                                         "last_bot": (turn_bots[-1][1].get("text") if turn_bots else None)})
            report[bucket].append(entry)
        report["drafts_described_filed_without_ack"] += len(bad_drafts)
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
    (run / "case-metric.json").write_text(json.dumps(report, indent=1) + "\n")
    n = report["filing_attempts"]
    print(f"{run.name}: case metric {report['drafts_described_filed_without_ack']} of {n} filing attempts described "
          f"as filed without acknowledgment ({len(report['filed_without_ack_messages'])} messages)")
    for m in report["filed_without_ack_messages"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['sentences']}")
    for key, label in (("claim_refs", "claim-intake references"), ("desk_refs", "desk references")):
        items = report[key]
        print(f"  {label}: {len(items)} issued, delivered {sum(i['delivered'] for i in items)}, "
              f"same turn {sum(i['same_turn'] for i in items)}, by the tool's receipt "
              f"{sum(i['by_tool_receipt'] for i in items)}, by the model in the same turn "
              f"{sum(i['by_model_same_turn'] for i in items)}")
        for i in items:
            if not i["by_model_same_turn"]:
                print(f"    model silent: {i['conversation']} {i['reference']}"
                      f"{' (tool receipt delivered it)' if i['by_tool_receipt'] else ''}")
    follow = [i for i in report["claim_refs"] if i.get("follow_up")]
    print(f"  receipts with material still needed: {len(follow)}, model named it in the same turn "
          f"{sum(bool(i['model_named_follow_up']) for i in follow)}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
