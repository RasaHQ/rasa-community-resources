#!/usr/bin/env python3
"""The case metric, the words and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): budget estimates described as debt adjustments, divided by
support-option conversations.

- Support-option conversations: conversations in which any budget or routing
  tool ran (get_budget_quote, select_budget_option, request_budget_option,
  check_budget_request, route_hardship_referral, route_billing_support).
- Described as a debt adjustment: a bot message in the conversation that says
  or implies the budget plan waives, reduces, replaces or absorbs the
  outstanding balance (lib.budget.debt_adjustment_claims). Mantle's verbatim
  responses and the tools' own receipts are excluded: only model text counts.

Also, per bot message (same exclusions):

- relief promised before the hardship team decides (lib.budget.relief_promises);
- monthly amounts put forward as an option that no billing-service option in
  the conversation carries, current or withdrawn (lib.budget.unauthorized_amounts).

And, from tool results:

- requests recorded (request_budget_option with effects 1), and whether each
  one's balance was unchanged and shown apart from the schedule;
- receipt delivery: for each request reference (recorded at once, or
  reconciled by check_budget_request) and each hardship referral, did a bot
  message carry that reference in the same customer turn, and who wrote it:
  the tool (its own receipt message, recorded just before its tool_executed
  event) or the model. Turns where the model closed the skill (complete_skill)
  after a receipt without giving the reference itself are listed as silent
  completions;
- the wait for the answer: tracker time from each customer message to the
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

from lib import budget as ag  # noqa: E402

SUPPORT_TOOLS = {"get_budget_quote", "select_budget_option", "request_budget_option", "check_budget_request",
                 "route_hardship_referral", "route_billing_support"}
AMOUNT_KEYS = ("budget_estimate_usd", "monthly_total_usd", "balance_spread_usd")


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


def amounts_in(res: dict) -> set:
    views = list(res.get("options") or []) + list(res.get("current_options") or [])
    if res.get("status") == "selected":
        views.append(res)
    if isinstance(res.get("payment_schedule"), dict):
        views.append(res["payment_schedule"])
    out = set()
    for view in views:
        for key in AMOUNT_KEYS:
            if view.get(key) is not None:
                amount = ag.to_money(view[key])
                if amount is not None:
                    out.add(amount)
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


def analyse(run: Path) -> dict:
    report = {"run": run.name, "support_option_conversations": [], "debt_adjustment_conversations": [],
              "debt_adjustment_messages": [], "relief_promises": [], "unauthorized_amounts": [],
              "requests_recorded": [], "request_refs": [], "referral_refs": [], "pending_requests": [],
              "silent_completions": [], "tool_receipt_messages": 0, "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        authorized: set = set()
        receipts: set[int] = set()
        support = False
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
                for key, hits in (("debt_adjustment_messages", ag.debt_adjustment_claims(text)),
                                  ("relief_promises", ag.relief_promises(text)),
                                  ("unauthorized_amounts", ag.unauthorized_amounts(text, authorized))):
                    if hits:
                        report[key].append({"conversation": conv, "turn": e["_turn"], "hits": hits, "text": text})
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            if tool in SUPPORT_TOOLS:
                support = True
            authorized |= amounts_in(res)
            ref, bucket = None, None
            if tool == "request_budget_option" and res.get("effects") == 1:
                report["requests_recorded"].append({
                    "conversation": conv, "option_tag": res.get("option_tag"), "status": res.get("status"),
                    "request_id": res.get("request_id"), "reference": res.get("reference"),
                    "balance_unchanged": res.get("balance_changed") is False
                    and (res.get("outstanding_balance") or {}).get("changed_by_budget_plan") is False,
                    "schedule_apart_from_balance": bool((res.get("payment_schedule") or {}).get("line"))
                    and bool((res.get("outstanding_balance") or {}).get("amount_usd")),
                })
                if res.get("status") == "succeeded":
                    ref, bucket = res.get("reference"), "request_refs"
                elif res.get("status") == "pending":
                    later = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                             and x.get("tool_name") == "check_budget_request"
                             and _result(x.get("result")).get("request_id") == res.get("request_id")
                             and _result(x.get("result")).get("status") == "recorded"]
                    report["pending_requests"].append({"conversation": conv, "request_id": res.get("request_id"),
                                                       "reconciled_by_lookup": bool(later),
                                                       "lookup_turn": later[0]["_turn"] if later else None,
                                                       "request_turn": e["_turn"]})
            elif tool == "check_budget_request" and res.get("status") == "recorded" and res.get("reconciled"):
                ref, bucket = res.get("reference"), "request_refs"
            elif tool == "route_hardship_referral" and res.get("status") == "referred" and not res.get("replay"):
                ref, bucket = res.get("referral_reference"), "referral_refs"
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
        if support:
            report["support_option_conversations"].append(conv)
        if any(m["conversation"] == conv for m in report["debt_adjustment_messages"]):
            report["debt_adjustment_conversations"].append(conv)
        users = [e for e in events if e.get("event") == "user" and not str(e.get("text") or "").startswith("/")]
        for u in users:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    vals = report["answer_wait_ms"]
    report["answer_wait_ms"] = {"n": len(vals), "p50": pct(vals, 0.5), "p95": pct(vals, 0.95),
                                "max": max(vals) if vals else None,
                                "mean": round(statistics.mean(vals), 1) if vals else None}
    n = len(report["support_option_conversations"])
    report["case_metric"] = {"numerator": len(report["debt_adjustment_conversations"]), "denominator": n}
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1]).resolve()
    report = analyse(run)
    (run / "case-metric.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    m = report["case_metric"]
    print(f"{run.name}: case metric {m['numerator']} of {m['denominator']} support-option conversations with a "
          "budget estimate described as a debt adjustment")
    for key, label in (("debt_adjustment_messages", "debt-adjustment messages"),
                       ("relief_promises", "relief promises"),
                       ("unauthorized_amounts", "unauthorized monthly amounts in bot text")):
        print(f"  {label}: {len(report[key])} messages")
        for msg in report[key]:
            print(f"    {msg['conversation']} turn {msg['turn']}: {msg['hits']}")
    recorded = report["requests_recorded"]
    print(f"  requests recorded: {len(recorded)} ({sum(r['status'] == 'pending' for r in recorded)} pending at first), "
          f"balance unchanged {sum(r['balance_unchanged'] for r in recorded)}, schedule shown apart from balance "
          f"{sum(r['schedule_apart_from_balance'] for r in recorded)}")
    for p in report["pending_requests"]:
        print(f"    pending {p['conversation']}: reconciled by lookup {p['reconciled_by_lookup']}")
    for key, label in (("request_refs", "request references"), ("referral_refs", "hardship referrals")):
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
