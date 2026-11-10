#!/usr/bin/env python3
"""The case metric, the words and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): scheduled moves causing premature current-service
closure, divided by move requests.

- Move requests: distinct drafts start_move_draft opened (status drafted or
  needs_review), in every conversation of the run.
- Premature closure, per draft: any tool result in the conversation that
  reports the service being left as not on now; a scheduled order whose
  current service does not stay on through the order's own move-out day; or
  a current service ending on or before the fixture's today, or before the
  move-out day of the latest scheduled order for that service.

The words, per bot message (Mantle's verbatim responses and the tools' own
receipts excluded): sentences saying the current supply is already off
(lib.moves.closure_claims, straight and typographic apostrophes).

Receipt delivery: for each move-order reference a tool issued (a first
scheduling, an amendment, or an acknowledgment found on check) and each
review reference, did a bot message carry that reference in the same
customer turn, and who wrote it: the tool (its own receipt message, recorded
just before its tool_executed event) or the model. Turns where the model
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
import statistics
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import moves as ag  # noqa: E402

TODAY = ag.AS_OF.isoformat()


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
    """Tracker events with the customer turn each followed (0 = first customer message)."""
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
            expected = ag.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def premature(current: dict, scheduled_out: str | None) -> str | None:
    """Why this current-service view is a premature closure, or None."""
    if not current:
        return None
    if current.get("on_now") is not True or current.get("status") != "active":
        return "reported not on now"
    through = current.get("stays_on_through")
    if through is not None and through <= TODAY:
        return f"ends {through}, on or before today"
    if through is not None and scheduled_out is not None and through < scheduled_out:
        return f"ends {through}, before the scheduled move-out {scheduled_out}"
    return None


def analyse(run: Path) -> dict:
    report = {"run": run.name, "move_requests": [], "premature_closures": [], "closure_claims": [],
              "order_refs": [], "review_refs": [], "silent_completions": [], "tool_receipt_messages": 0,
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        receipts: set[int] = set()
        drafts: dict[str, str] = {}  # draft id -> service point
        scheduled: dict[str, str] = {}  # service point -> move-out of the latest scheduled order
        flagged: set[str] = set()
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot":
                if is_tool_receipt(events, i):
                    receipts.add(i)
                    report["tool_receipt_messages"] += 1
                    continue
                if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                    continue
                hits = ag.closure_claims(e.get("text") or "")
                if hits:
                    report["closure_claims"].append({"conversation": conv, "turn": e["_turn"], "hits": hits,
                                                     "text": e.get("text")})
                continue
            if kind != "tool_executed" or e.get("tool_name") == "resolve_tool_confirmation":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            current = res.get("current_service") or {}
            sp = current.get("service_point")
            if tool in ("start_move_draft", "update_move_draft") and res.get("draft_id") and sp:
                if tool == "start_move_draft" and res.get("status") in ("drafted", "needs_review") \
                        and res["draft_id"] not in drafts:
                    report["move_requests"].append({"conversation": conv, "draft_id": res["draft_id"],
                                                    "status": res["status"]})
                drafts.setdefault(res["draft_id"], sp)
            order_ok = tool in ("submit_move_order", "check_move_order") and res.get("status") == "succeeded"
            if order_ok and sp:
                if current.get("stays_on_through") != res.get("move_out_date"):
                    why = f"order move-out {res.get('move_out_date')} but service shown through {current.get('stays_on_through')}"
                else:
                    why = None
                scheduled[sp] = res.get("move_out_date")
            else:
                why = None
            why = why or premature(current, scheduled.get(sp) if sp else None)
            if why:
                affected = [d for d, s in drafts.items() if s == sp] or [f"(no draft) {sp}"]
                for d in affected:
                    if (conv, d) not in flagged:
                        flagged.add((conv, d))
                        report["premature_closures"].append({"conversation": conv, "draft_id": d, "tool": tool,
                                                             "why": why})
            ref, bucket = None, None
            if order_ok and (tool == "submit_move_order" and not res.get("replay")
                             or tool == "check_move_order" and res.get("acknowledged_on_check")):
                ref, bucket = f"{res.get('order_ref')} r{res.get('order_revision')}", "order_refs"
                plain_ref = res.get("order_ref")
            elif tool == "route_move_review" and res.get("status") == "routed" and not res.get("replay"):
                ref = plain_ref = res.get("review_ref")
                bucket = "review_refs"
            if not ref or any(r["reference"] == ref for r in report[bucket] if r["conversation"] == conv):
                continue
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]
            carrying = [(j, b) for j, b in turn_bots + later_bots if plain_ref in (b.get("text") or "")]
            by_model_same_turn = [b for j, b in turn_bots if j not in receipts and plain_ref in (b.get("text") or "")]
            entry = {"conversation": conv, "tool": tool, "reference": ref,
                     "delivered": bool(carrying),
                     "same_turn": any(events[j]["_turn"] == turn for j, _ in carrying),
                     "by_tool_receipt": any(j in receipts for j, _ in carrying if events[j]["_turn"] == turn),
                     "by_model_same_turn": bool(by_model_same_turn)}
            completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                         and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
            if completes and not by_model_same_turn:
                report["silent_completions"].append({"conversation": conv, "reference": ref,
                                                     "last_bot": (turn_bots[-1][1].get("text") if turn_bots else None)})
            report[bucket].append(entry)
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
    requests = len(report["move_requests"])
    print(f"{run.name}: case metric {len(report['premature_closures'])} of {requests} move requests with a premature "
          "current-service closure")
    for p in report["premature_closures"]:
        print(f"    {p['conversation']} {p['draft_id']}: {p['why']} ({p['tool']})")
    print(f"  closure claims in bot text: {len(report['closure_claims'])} messages")
    for m in report["closure_claims"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['hits']}")
    for key, label in (("order_refs", "move-order references"), ("review_refs", "review references")):
        items = report[key]
        print(f"  {label}: {len(items)} issued, delivered {sum(i['delivered'] for i in items)}, "
              f"same turn {sum(i['same_turn'] for i in items)}, by the tool's receipt "
              f"{sum(i['by_tool_receipt'] for i in items)}, by the model in the same turn "
              f"{sum(i['by_model_same_turn'] for i in items)}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
