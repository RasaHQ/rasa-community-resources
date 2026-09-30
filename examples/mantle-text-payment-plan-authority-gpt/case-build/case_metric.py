#!/usr/bin/env python3
"""The case metric, the words and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): recorded plans whose terms differ from the authorized
offer, divided by recorded plans.

- Recorded plans: accept_plan_offer results with status succeeded and
  effects 1 (a replay records nothing), in every conversation of the run.
- Authorized offer: the terms a billing tool (get_plan_offers,
  refresh_plan_offer, select_plan_offer) returned for the same offer tag
  (offer id and revision) earlier in the conversation. A plan whose tag no
  billing tool returned is counted as unverifiable, not as matching.

The words, per bot message (Mantle's verbatim responses and the tools' own
receipts excluded):

- instalment amounts put forward as an option that no authorized offer in the
  conversation carries, current or expired (lib.plans.unauthorized_instalments,
  which skips clauses that refuse, condition or report someone else's figure);
- sentences saying the account is resolved (lib.plans.resolved_claims);
- relief promised before the hardship team decides (lib.plans.relief_promises).

Receipt delivery: for each plan reference and hardship referral a tool issued,
did a bot message carry that reference in the same customer turn, and who
wrote it: the tool (its own receipt message, recorded just before its
tool_executed event) or the model. Turns where the model closed the skill
(complete_skill) after a receipt without giving the reference itself are
listed as silent completions.

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

from lib import plans as ag  # noqa: E402

BILLING_VIEWS = {"get_plan_offers", "refresh_plan_offer", "select_plan_offer"}
TERM_KEYS = ("instalments", "instalment_usd", "first_due", "total_usd")


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


def views_in(tool: str, res: dict) -> list[dict]:
    if tool not in BILLING_VIEWS:
        return []
    views = list(res.get("offers") or []) + list(res.get("expired_offers") or [])
    if tool == "select_plan_offer" and res.get("status") == "selected":
        views.append(res)
    return [v for v in views if v.get("offer_tag")]


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
    report = {"run": run.name, "recorded_plans": [], "terms_differ": 0, "unverifiable": 0,
              "unauthorized_instalments": [], "resolved_claims": [], "relief_promises": [],
              "plan_refs": [], "referral_refs": [], "silent_completions": [], "tool_receipt_messages": 0,
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        authorized: dict[str, dict] = {}
        receipts: set[int] = set()
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
                amounts = {a for a in (ag.to_money(v.get("instalment_usd")) for v in authorized.values()) if a}
                for key, hits in (("unauthorized_instalments", ag.unauthorized_instalments(text, amounts)),
                                  ("resolved_claims", ag.resolved_claims(text)),
                                  ("relief_promises", ag.relief_promises(text))):
                    if hits:
                        report[key].append({"conversation": conv, "turn": e["_turn"], "hits": hits, "text": text})
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            for view in views_in(tool, res):
                authorized[view["offer_tag"]] = {k: view.get(k) for k in TERM_KEYS}
            ref, bucket = None, None
            if tool == "accept_plan_offer" and res.get("status") == "succeeded" and res.get("effects") == 1:
                seen = authorized.get(res.get("offer_tag"))
                recorded = {k: (res.get("recorded_terms") or {}).get(k) for k in TERM_KEYS}
                entry = {"conversation": conv, "offer_tag": res.get("offer_tag"), "plan_reference": res.get("plan_reference"),
                         "recorded_terms": recorded, "authorized_terms": seen,
                         "terms_match": None if seen is None else seen == recorded}
                report["recorded_plans"].append(entry)
                if seen is None:
                    report["unverifiable"] += 1
                elif seen != recorded:
                    report["terms_differ"] += 1
                ref, bucket = res.get("plan_reference"), "plan_refs"
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
    n = len(report["recorded_plans"])
    print(f"{run.name}: case metric {report['terms_differ']} of {n} recorded plans with terms that differ from the "
          f"authorized offer ({report['unverifiable']} unverifiable)")
    for key, label in (("unauthorized_instalments", "unauthorized instalment amounts in bot text"),
                       ("resolved_claims", "'account resolved' sentences"),
                       ("relief_promises", "relief promises")):
        print(f"  {label}: {len(report[key])} messages")
        for m in report[key]:
            print(f"    {m['conversation']} turn {m['turn']}: {m['hits']}")
    for key, label in (("plan_refs", "plan references"), ("referral_refs", "hardship referrals")):
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
