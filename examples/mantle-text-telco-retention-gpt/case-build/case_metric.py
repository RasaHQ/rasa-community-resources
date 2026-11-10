#!/usr/bin/env python3
"""The case metric, the words and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): offer prompts after a clear refusal, divided by sessions
containing refusal.

- A session contains a refusal from the first customer message that
  lib.retention.refusal_in matches ("stop", "no more offers", "just cancel",
  "continue to cancellation", "/stop", straight and typographic apostrophes),
  or the first bare "No" given in answer to the engine's offer question.
- An offer prompt after that point is any of: the engine's offer question
  (a bot message stamped utter_offer_or_cancel), a get_retention_offer result
  with status "offer", or a model-written bot message that puts an offer in
  front of the customer (lib.retention.offer_prompts; Mantle's verbatim
  responses and the tools' own receipts excluded).

Also, per run:

- Cancellation requests recorded, and where each went: the cancellations
  desk, held for the retention operations owner, or a sales queue (the
  contract's evidence: "cancellation reaches the correct service rather than
  another sales loop").
- Model-written sentences that call a service or account cancelled or
  closed (lib.retention.closure_claims): the cancellation intake is not the
  closure.
- Prices or discounts in model-written offer sentences that no earlier tool
  result carried (lib.retention.invented_terms).
- Receipt delivery: for each cancellation, offer, withdrawal and review
  reference a tool issued, did a bot message carry it in the same customer
  turn, and who wrote it: the tool (its own receipt, recorded just before
  its tool_executed event) or the model. Turns where the model closed the
  skill (complete_skill) after a receipt without giving the reference itself
  are listed as silent completions.
- The wait for the answer: tracker time from each customer message to the
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

from lib import retention as jm  # noqa: E402


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
        if e.get("event") == "user" and not str(e.get("text") or "").startswith("/session_start"):
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
            expected = jm.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def refusal_index(events: list[dict]) -> tuple[int | None, str | None]:
    asked = False
    for i, e in enumerate(events):
        if e.get("event") == "bot" and (e.get("metadata") or {}).get("utter_action") == jm.CONFIRM_UTTER:
            asked = True
        elif e.get("event") == "user" and e["_turn"] >= 0:
            text = e.get("text") or ""
            found = jm.refusal_in(text)
            if found:
                return i, found
            if asked and jm._BARE_NO_RE.match(jm.plain(text)):
                return i, text.strip()
            asked = False
    return None, None


RECEIPT_TOOLS = {
    "record_cancellation_request": lambda r: r.get("status") == "recorded" and not r.get("replay"),
    "accept_retention_offer": lambda r: r.get("status") == "succeeded" and not r.get("replay"),
    "withdraw_contact": lambda r: r.get("status") == "recorded" and not r.get("replay"),
}


def analyse(run: Path) -> dict:
    report = {"run": run.name, "sessions_with_refusal": [], "offer_prompts_after_refusal": [],
              "offer_prompts_without_refusal": 0, "cancellation_requests": [], "closure_claims": [],
              "invented_terms": [], "references": [], "silent_completions": [], "tool_receipt_messages": 0,
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        receipts = {i for i, e in enumerate(events) if e.get("event") == "bot" and is_tool_receipt(events, i)}
        report["tool_receipt_messages"] += len(receipts)
        refused_at, refusal = refusal_index(events)
        if refused_at is not None:
            report["sessions_with_refusal"].append({"conversation": conv, "turn": events[refused_at]["_turn"],
                                                    "refusal": refusal})
        tool_texts: list[str] = []
        for i, e in enumerate(events):
            kind = e.get("event")
            after = refused_at is not None and i > refused_at
            prompt = None
            if kind == "bot":
                meta = e.get("metadata") or {}
                text = e.get("text") or ""
                if meta.get("utter_action") == jm.CONFIRM_UTTER:
                    prompt = {"kind": "engine offer question", "text": text}
                elif i not in receipts and meta.get("mantle_response_source") != "verbatim":
                    hits = jm.offer_prompts(text)
                    if hits:
                        prompt = {"kind": "model text", "hits": hits, "text": text}
                    claims = jm.closure_claims(text)
                    if claims:
                        report["closure_claims"].append({"conversation": conv, "turn": e["_turn"], "hits": claims,
                                                         "text": text})
                    invented = jm.invented_terms(text, tool_texts)
                    if invented:
                        report["invented_terms"].append({"conversation": conv, "turn": e["_turn"],
                                                         "terms": invented, "text": text})
            elif kind == "tool_executed":
                tool, res = e.get("tool_name"), _result(e.get("result"))
                tool_texts.append(json.dumps(res, ensure_ascii=False))
                if tool == "get_retention_offer" and res.get("status") == "offer":
                    prompt = {"kind": "get_retention_offer returned an offer", "offer_id": res.get("offer_id")}
                if tool == "record_cancellation_request" and res.get("status") == "recorded" \
                        and not res.get("replay"):
                    report["cancellation_requests"].append({"conversation": conv, "reference": res.get("reference"),
                                                            "service": res.get("service"), "route": res.get("route")})
                if tool in RECEIPT_TOOLS and RECEIPT_TOOLS[tool](res):
                    refs = [res.get("reference")] + ([res["review_ref"]] if res.get("review_ref") else [])
                    for ref in refs:
                        if not ref or any(r["reference"] == ref and r["conversation"] == conv
                                          for r in report["references"]):
                            continue
                        turn = e["_turn"]
                        turn_bots = [(j, b) for j, b in enumerate(events)
                                     if b.get("event") == "bot" and b["_turn"] == turn]
                        carrying = [j for j, b in turn_bots if ref in (b.get("text") or "")]
                        # The engine's offer question also names the cancellation request; it is
                        # a verbatim response, not the model's words.
                        by_model = [j for j in carrying if j not in receipts
                                    and (events[j].get("metadata") or {}).get("mantle_response_source") != "verbatim"
                                    and not (events[j].get("metadata") or {}).get("utter_action")]
                        report["references"].append({
                            "conversation": conv, "tool": tool, "reference": ref,
                            "same_turn": bool(carrying),
                            "by_tool_receipt": any(j in receipts for j in carrying),
                            "by_model_same_turn": bool(by_model)})
                        completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                                     and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
                        if completes and not by_model:
                            report["silent_completions"].append({
                                "conversation": conv, "reference": ref,
                                "last_bot": turn_bots[-1][1].get("text") if turn_bots else None})
            if prompt is None:
                continue
            if after:
                report["offer_prompts_after_refusal"].append({"conversation": conv, "turn": e["_turn"], **prompt})
            else:
                report["offer_prompts_without_refusal"] += 1
        users = [e for e in events if e.get("event") == "user" and e["_turn"] >= 0]
        for u in users:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    sessions = len(report["sessions_with_refusal"])
    report["case_metric"] = {"offer_prompts_after_refusal": len(report["offer_prompts_after_refusal"]),
                             "sessions_with_refusal": sessions,
                             "value": (round(len(report["offer_prompts_after_refusal"]) / sessions, 3)
                                       if sessions else None)}
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
    m = report["case_metric"]
    print(f"{run.name}: case metric {m['offer_prompts_after_refusal']} offer prompts after a clear refusal / "
          f"{m['sessions_with_refusal']} sessions containing refusal = {m['value']}")
    for p in report["offer_prompts_after_refusal"]:
        print(f"    {p['conversation']} turn {p['turn']}: {p['kind']}")
    print(f"  offer prompts in sessions before or without a refusal: {report['offer_prompts_without_refusal']}")
    routes: dict[str, int] = {}
    for c in report["cancellation_requests"]:
        routes[c["route"]] = routes.get(c["route"], 0) + 1
    print(f"  cancellation requests recorded: {len(report['cancellation_requests'])} {routes}")
    print(f"  closure claims in model text: {len(report['closure_claims'])}")
    for c in report["closure_claims"]:
        print(f"    {c['conversation']} turn {c['turn']}: {c['hits']}")
    print(f"  invented terms in model offer text: {len(report['invented_terms'])}")
    for c in report["invented_terms"]:
        print(f"    {c['conversation']} turn {c['turn']}: {c['terms']}")
    refs = report["references"]
    print(f"  references issued: {len(refs)}, same turn {sum(r['same_turn'] for r in refs)}, by the tool's receipt "
          f"{sum(r['by_tool_receipt'] for r in refs)}, by the model in the same turn "
          f"{sum(r['by_model_same_turn'] for r in refs)}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
