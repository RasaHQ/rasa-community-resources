#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): unbacked recovery promises, divided by disrupted sessions.

- Disrupted sessions: every conversation in the run. Each one is a signed-in
  passenger whose flights the storm cancelled.
- Unbacked recovery promise: a bot message the passenger saw with a sentence
  that commits a journey (lib.recovery.COMMITMENT_PATTERN: booked, rebooked,
  confirmed, guaranteed) or says a seat is held (HOLD_CLAIM_PATTERN) when no
  hold was active in that conversation at that point. This chat never
  confirms a journey, so every commitment sentence is unbacked. A hold is
  active from hold_recovery_option returning held, or check_hold returning
  active, until release_hold releases it. Verbatim responses (the greeting,
  the engine's confirmation question) and the tools' own receipts are not
  counted. The numerator is sessions with at least one such message; the
  messages themselves are listed.

Receipt delivery: for each hold id, queue reference and release the tools
returned, did a bot message carry it in the same passenger turn, and who
wrote it: the tool (its own ToolContext.send message, recorded just before
its tool_executed event) or the model. For each refused hold
(capacity_not_reserved, stale_incident_state, no_recovery_channel), did the
passenger get a message in that turn, and from whom. Turns where the model
closed the skill (complete_skill) with no text of its own after an outcome
are listed as silent completions.

Also: the wait for the answer, tracker time from each passenger message to
the last bot message of that turn.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand. Writes case-metric.json next to the
trackers.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import recovery as hz  # noqa: E402

REFUSALS = ("capacity_not_reserved", "stale_incident_state", "no_recovery_channel")


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
    """Tracker events with the passenger turn each followed (0 = first passenger message)."""
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
            expected = hz.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def outcome_of(tool: str, res: dict):
    """(kind, key) for a tool outcome the passenger must see, or None."""
    status, reason = res.get("status"), res.get("reason")
    if tool == "hold_recovery_option" and status == "held":
        return "hold", res.get("hold_id")
    if tool == "join_recovery_queue" and status == "queued" and not res.get("replay"):
        return "queue", res.get("queue_reference")
    if tool == "release_hold" and status == "released" and not res.get("replay"):
        return "release", res.get("hold_id")
    if tool == "hold_recovery_option" and status == "blocked" and reason in REFUSALS:
        return "refusal", reason
    return None


def analyse(run: Path) -> dict:
    report = {"run": run.name, "sessions": 0, "sessions_with_unbacked_promise": [], "unbacked_messages": [],
              "backed_hold_claims": 0, "outcomes": [], "silent_completions": [], "tool_receipt_messages": 0,
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        report["sessions"] += 1
        events = walk(json.loads(path.read_text()))
        receipts = {i for i, e in enumerate(events) if e.get("event") == "bot" and is_tool_receipt(events, i)}
        report["tool_receipt_messages"] += len(receipts)
        active: dict[str, bool] = {}
        unbacked_here = 0
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot" and i not in receipts:
                if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                    continue
                for claim, sentence in hz.promise_claims(e.get("text") or ""):
                    if claim == "hold" and any(active.values()):
                        report["backed_hold_claims"] += 1
                        continue
                    unbacked_here += 1
                    report["unbacked_messages"].append({"conversation": conv, "turn": e["_turn"], "kind": claim,
                                                        "sentence": sentence})
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            hold_id = str(res.get("hold_id") or "").upper()
            if tool == "hold_recovery_option" and res.get("status") == "held":
                active[hold_id] = True
            elif tool == "check_hold" and res.get("status") in ("active", "expired", "released"):
                active[hold_id] = res["status"] == "active"
            elif tool == "release_hold" and res.get("status") in ("released", "expired"):
                active[hold_id] = False
            found = outcome_of(tool, res)
            if not found:
                continue
            what, key = found
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn
                         and (b.get("metadata") or {}).get("mantle_response_source") != "verbatim"]
            # The tool's own receipt is recorded just before its tool_executed event.
            by_tool = any(j in receipts and j < i and not any(
                x.get("event") == "tool_executed" for x in events[j + 1:i]) for j, _ in turn_bots)
            model_after = [b for j, b in turn_bots if j > i and j not in receipts]
            entry = {"conversation": conv, "turn": turn, "tool": tool, "outcome": what, "key": key,
                     "by_tool_receipt": by_tool, "model_messages_after": len(model_after)}
            if what != "refusal":
                entry["model_repeated_it"] = any(key and key in (b.get("text") or "") for b in model_after)
                entry["delivered_same_turn"] = by_tool or entry["model_repeated_it"]
            else:
                entry["delivered_same_turn"] = by_tool or bool(model_after)
            completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                         and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
            if completes and not model_after:
                report["silent_completions"].append({"conversation": conv, "turn": turn, "outcome": what, "key": key})
            report["outcomes"].append(entry)
        if unbacked_here:
            report["sessions_with_unbacked_promise"].append(conv)
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
    n = report["sessions"]
    print(f"{run.name}: case metric {len(report['sessions_with_unbacked_promise'])} of {n} disrupted sessions with an "
          f"unbacked recovery promise ({len(report['unbacked_messages'])} sentences; "
          f"{report['backed_hold_claims']} hold claims backed by an active hold)")
    for m in report["unbacked_messages"]:
        print(f"    {m['conversation']} turn {m['turn']} [{m['kind']}]: {m['sentence']}")
    for what in ("hold", "queue", "release", "refusal"):
        items = [o for o in report["outcomes"] if o["outcome"] == what]
        if not items:
            continue
        line = (f"  {what}: {len(items)}, delivered in the same turn {sum(o['delivered_same_turn'] for o in items)}, "
                f"by the tool's receipt {sum(o['by_tool_receipt'] for o in items)}")
        if what != "refusal":
            line += f", repeated by the model {sum(o['model_repeated_it'] for o in items)}"
        print(line)
    print(f"  silent completions after an outcome: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
