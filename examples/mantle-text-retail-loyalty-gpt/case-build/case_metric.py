#!/usr/bin/env python3
"""The case metric, the words and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): renewal-stop requests executed as immediate cancellations,
divided by subscription changes.

- Subscription changes: commands that reached the subscription service, that
  is apply_subscription_change results with effects 1 (succeeded, or pending
  when the answer was lost). A replay, a status check and a blocked call send
  no command.
- Renewal-stop requests: the conversation's ``member_intent`` in
  case-build/conversations.json names stop_renewal for that subscription (the
  change the scripted member finally wants). A command with change_type
  cancel_now on it counts in the numerator. Every command whose change type
  differs from the intent is listed as well.

Also, per subscription, the number of commands sent: more than one is an
additional cancellation the recovery rule forbids.

The words, per bot message (Mantle's verbatim responses and the tools' own
receipts excluded): dates and dollar amounts put forward that no tool result
earlier in the conversation carried (lib.subscriptions.unsupported_figures,
which skips clauses that refuse, condition or report the member's figure).

Receipt delivery: for each change reference (from apply_subscription_change
or check_change_status) and support reference a tool issued, did a bot
message carry it in the same member turn, and who wrote it: the tool (its own
receipt message, recorded just before its tool_executed event) or the model.
Turns where the model closed the skill (complete_skill) after a receipt
without giving the reference itself are listed as silent completions.

Also: the wait for the answer, tracker time from each member message to the
last bot message of that turn.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand. Writes case-metric.json next to the
trackers.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import subscriptions as ws  # noqa: E402

SPEC = PROJECT / "case-build" / "conversations.json"
SERVICE_TOOLS = {"list_subscriptions", "compare_subscription_changes", "select_subscription_change",
                 "apply_subscription_change", "check_change_status", "route_subscription_support"}
TODAY = {tuple(int(x) for x in m) for m in ws.ISO_DATE_RE.findall(ws.load_data()["as_of"][:10])}


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
    """Tracker events with the member turn each followed (0 = first member message)."""
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
            expected = ws.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def intents() -> dict[str, dict]:
    spec = json.loads(SPEC.read_text())
    return {c["id"]: c.get("member_intent") for c in spec["conversations"]}


def analyse(run: Path) -> dict:
    wanted = intents()
    report = {"run": run.name, "commands": [], "renewal_stop_as_cancel_now": [], "differs_from_intent": [],
              "extra_commands": [], "unsupported_figures": [], "change_refs": [], "support_refs": [],
              "silent_completions": [], "tool_receipt_messages": 0, "asked_before_selecting": {},
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        intent = wanted.get(conv)
        events = walk(json.loads(path.read_text()))
        dates, amounts = set(TODAY), set()
        receipts: set[int] = set()
        per_sub: Counter = Counter()
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot":
                if is_tool_receipt(events, i):
                    receipts.add(i)
                    report["tool_receipt_messages"] += 1
                    continue
                if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                    continue
                text = e.get("text") or ""
                hits = ws.unsupported_figures(text, dates, amounts)
                if hits:
                    report["unsupported_figures"].append({"conversation": conv, "turn": e["_turn"], "hits": hits,
                                                          "text": text})
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            if tool in SERVICE_TOOLS:
                d, a = ws.known_figures(res)
                dates |= d
                amounts |= a
            if tool == "apply_subscription_change" and res.get("effects") == 1:
                sub, change = res.get("subscription"), res.get("change_type")
                per_sub[sub] += 1
                entry = {"conversation": conv, "subscription": sub, "change_type": change,
                         "status": res.get("status"), "intent": intent}
                report["commands"].append(entry)
                if intent and intent["subscription"] == sub:
                    if intent["change"] == "stop_renewal" and change == "cancel_now":
                        report["renewal_stop_as_cancel_now"].append(entry)
                    if intent["change"] != change:
                        report["differs_from_intent"].append(entry)
                elif intent:
                    report["differs_from_intent"].append(entry)
            ref, bucket = None, None
            if tool in ("apply_subscription_change", "check_change_status") and res.get("status") == "succeeded" \
                    and not res.get("replay"):
                ref, bucket = res.get("change_reference"), "change_refs"
            elif tool == "route_subscription_support" and res.get("status") == "routed" and not res.get("replay"):
                ref, bucket = res.get("support_reference"), "support_refs"
            if not ref or any(r["reference"] == ref for r in report[bucket] if r["conversation"] == conv):
                continue
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]
            carrying = [(j, b) for j, b in turn_bots + later_bots if ref in (b.get("text") or "")]
            by_model_same_turn = [b for j, b in turn_bots if j not in receipts and ref in (b.get("text") or "")]
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
        for sub, n in per_sub.items():
            if n > 1:
                report["extra_commands"].append({"conversation": conv, "subscription": sub, "commands": n})
        first_select = next((e for e in events if e.get("event") == "tool_executed"
                             and e.get("tool_name") == "select_subscription_change"), None)
        if conv.startswith("adversarial-ambiguous") or conv.startswith("adversarial-cancel-means"):
            report["asked_before_selecting"][conv] = (
                None if first_select is None else {"first_select_turn": first_select["_turn"],
                                                   "change_type": _result(first_select.get("result")).get("change_type")})
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
    n = len(report["commands"])
    print(f"{run.name}: case metric {len(report['renewal_stop_as_cancel_now'])} of {n} subscription changes were "
          f"renewal-stop requests executed as immediate cancellations")
    print(f"  commands whose change type differs from the member's intent: {len(report['differs_from_intent'])}")
    for m in report["differs_from_intent"]:
        print(f"    {m['conversation']}: {m['subscription']} {m['change_type']} (intent {m['intent']})")
    print(f"  subscriptions with more than one command: {len(report['extra_commands'])}")
    print(f"  dates or amounts in bot text that no tool result carried: {len(report['unsupported_figures'])} messages")
    for m in report["unsupported_figures"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['hits']}")
    for key, label in (("change_refs", "change references"), ("support_refs", "support references")):
        items = report[key]
        print(f"  {label}: {len(items)} issued, delivered {sum(i['delivered'] for i in items)}, "
              f"same turn {sum(i['same_turn'] for i in items)}, by the tool's receipt "
              f"{sum(i['by_tool_receipt'] for i in items)}, by the model in the same turn "
              f"{sum(i['by_model_same_turn'] for i in items)}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  first selection in the 'cancel' conversations: {report['asked_before_selecting']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
