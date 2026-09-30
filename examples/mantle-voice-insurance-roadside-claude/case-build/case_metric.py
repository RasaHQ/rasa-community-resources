#!/usr/bin/env python3
"""The case metric, receipt and refusal delivery, from a recorded run's trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py [case-build/results/<label>]

Metric (casebook): dispatches using an unconfirmed incident location, divided
by assistance requests.

- Assistance requests: request_dispatch calls that reached the tool (the
  engine's awaiting_confirmation and declined payloads are not requests, and
  a replay of a dispatched draft is not a new one).
- Dispatches: request_dispatch and request_next_provider results that sent a
  job to a provider (succeeded or pending, effects 1, not a replay).
- Using an unconfirmed incident location: a dispatch whose result does not
  show incident_location_confirmed exactly true, or whose place is not the
  place the latest confirmation question before it read back.
- Also against the script: a dispatch to a place other than where the
  script's vehicle is (`expected_location` below, taken from each
  conversation's checks).

Delivery, the question this build was asked: for each outcome the caller must
hear, did a bot message carry it, in the same caller turn, and who wrote it:
the tool (its own message through ToolContext.send) or the model.

- Receipts: an assistance reference from a dispatch (accepted, not yet
  accepted, or declined), matched by its six digits (spoken digits count).
- Refusals: a provider the caller asked for that could not do the job, and no
  suitable provider nearby, matched by the provider's name or the words "no
  provider" / "can't" / "nothing has been sent".
- Desk references: from route_dispatch_desk, matched by six digits.

A tool's own message is recorded just before its tool_executed event, so a
bot message that is exactly the text lib.roadside.customer_receipt gives for
the next tool result is the tool's. When the tool sent nothing (the
`receipt-in-result-only` variant), only the model can deliver it.

Also measured, never pass or fail: time mentions not backed by a provider's
estimate given earlier in the call ("invented estimates"), and "on the way"
claims before any provider accepted. And the wait for the answer: tracker
time from each caller user event to the last bot message of that turn.

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

from lib import roadside as hc  # noqa: E402

DEFAULT_RUN = PROJECT / "case-build" / "results" / "2026-09-30-claude-sonnet-5.5"
WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
         "six": "6", "seven": "7", "eight": "8", "nine": "9"}
DISPATCH_TOOLS = ("request_dispatch", "request_next_provider")
NUMBER_WORDS = {"five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30,
                "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "seventy": 70, "an": 60, "half an": 30}
TIME_RE = re.compile(r"(?i)\b(\d+|five|ten|fifteen|twenty-five|twenty|thirty|forty-five|forty|fifty|sixty|seventy"
                     r"|half an|an)\s+(minutes?|mins?|hours?)\b")
ON_WAY_RE = re.compile(r"(?i)\b(on (their|its|the|his|her) way|en route|coming to (you|get you)|headed (your way|to "
                       r"you)|will be (there|with you))\b")
NEGATION_RE = re.compile(r"(?i)\b(not|no|nobody|no one|isn't|aren't|yet|until|once|when|before|if)\b|n't\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
REFUSAL_RE = re.compile(r"(?i)(can't|cannot|can not|won't|unable|no (harborcover )?provider|nothing (has been|was) sent)")


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def digits_of(text: str) -> str:
    tokens = re.findall(r"[a-z]+|\d", (text or "").lower())
    return "".join(WORDS.get(tok, tok) for tok in tokens if tok.isdigit() or tok in WORDS)


def minutes(value: str, unit: str) -> int:
    n = int(value) if value.isdigit() else NUMBER_WORDS.get(value.lower(), 0)
    return n * 60 if unit.lower().startswith("hour") and value.lower() not in ("an", "half an") else n


def pct(values: list[float], q: float):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def walk(tracker: dict) -> list[dict]:
    """Tracker events with the caller turn each followed (0 = /session_start and the greeting)."""
    turn, out = 0, []
    for e in tracker.get("events", []):
        if e.get("event") == "user" and not str(e.get("text") or "").startswith("/"):
            turn += 1
        out.append({**e, "_turn": turn})
    return out


def tool_message_for(events: list[dict], i: int) -> tuple[str | None, dict | None]:
    """If bot event i is the message the next tool result produces, (tool name, result)."""
    for e in events[i + 1:]:
        kind = e.get("event")
        if kind in ("user", "bot"):
            return None, None
        if kind == "tool_executed":
            res = _result(e.get("result"))
            expected = hc.customer_receipt(e.get("tool_name"), res)
            if expected is not None and expected == events[i].get("text"):
                return e.get("tool_name"), res
            return None, None
    return None, None


def expected_locations(spec: dict) -> dict:
    """Where each script's vehicle really is: the location_ref its checks require a dispatch at."""
    out = {}
    for conv in spec.get("conversations", []):
        for check in conv.get("checks", []):
            loc = (check.get("result") or {}).get("location_ref")
            if check.get("type") == "tool_called" and isinstance(loc, str) and not loc.startswith("re:"):
                out[conv["id"]] = loc
    return out


def analyse(run: Path) -> dict:
    spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
    truth = expected_locations(spec)
    report = {"run": run.name, "assistance_requests": 0, "dispatches": 0, "dispatches_unconfirmed_location": [],
              "dispatches_not_where_the_vehicle_is": [], "blocked": {}, "receipts": [], "refusals": [],
              "desk_refs": [], "tool_messages": 0, "invented_estimates": [], "on_the_way_before_acceptance": [],
              "answer_wait_ms": []}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        tool_idx: dict[int, tuple[str, dict]] = {}
        for i, e in enumerate(events):
            if e.get("event") == "bot":
                tool, res = tool_message_for(events, i)
                if tool:
                    tool_idx[i] = (tool, res)
        report["tool_messages"] += len(tool_idx)
        etas: set[int] = set()
        accepted = False
        question_place = None
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "bot":
                meta = e.get("metadata") or {}
                text = e.get("text") or ""
                if meta.get("utter_action") == hc.CONFIRM_UTTER:
                    question_place = next((ref for ref, p in hc.load_data()["places"].items()
                                           if p["label"] in text), None)
                if i in tool_idx or meta.get("mantle_response_source") == "verbatim":
                    continue
                for m in TIME_RE.finditer(text):
                    if minutes(m.group(1), m.group(2)) not in etas:
                        report["invented_estimates"].append({"conversation": conv, "turn": e["_turn"], "text": text})
                        break
                if not accepted:
                    for sentence in SENTENCE_RE.split(text):
                        hit = ON_WAY_RE.search(sentence)
                        if hit and not NEGATION_RE.search(sentence[: hit.start()]):
                            report["on_the_way_before_acceptance"].append(
                                {"conversation": conv, "turn": e["_turn"], "sentence": sentence.strip()})
                            break
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            status = res.get("status")
            if res.get("provider_acceptance") == "accepted":
                accepted = True
            if (res.get("arrival_estimate") or {}).get("minutes") is not None:
                etas.add(res["arrival_estimate"]["minutes"])
            if tool == "request_dispatch" and status in ("succeeded", "pending", "blocked") and not res.get("replay"):
                report["assistance_requests"] += 1
            if tool in DISPATCH_TOOLS and status == "blocked":
                report["blocked"].setdefault(res.get("reason"), []).append(conv)
            sent = tool in DISPATCH_TOOLS and status in ("succeeded", "pending") and not res.get("replay")
            if sent:
                report["dispatches"] += 1
                facts = res.get("facts") or {}
                place = res.get("location_ref")
                if facts.get("incident_location_confirmed") is not True or (
                        tool == "request_dispatch" and place != question_place):
                    report["dispatches_unconfirmed_location"].append({"conversation": conv, "place": place,
                                                                      "question_read": question_place})
                if conv in truth and place != truth[conv]:
                    report["dispatches_not_where_the_vehicle_is"].append({"conversation": conv, "place": place,
                                                                          "vehicle_at": truth[conv]})
            # What the caller must hear from this result, and how to recognise it in a bot message.
            bucket, needle = None, None
            if sent or (tool == "check_dispatch" and status == "succeeded" and not res.get("replay")):
                bucket, needle = "receipts", re.sub(r"\D", "", res.get("assistance_ref") or "")
            elif tool == "route_dispatch_desk" and status == "routed":
                bucket, needle = "desk_refs", re.sub(r"\D", "", res.get("desk_ref") or "")
            elif tool in ("start_dispatch_draft", "update_dispatch_draft") and (
                    (res.get("preferred_provider") or {}).get("known") and not res["preferred_provider"]["used"]
                    or res.get("no_suitable_provider_nearby")):
                bucket = "refusals"
            elif tool in DISPATCH_TOOLS and status == "blocked" and res.get("reason") == "unsuitable_provider":
                bucket = "refusals"
            if bucket is None:
                continue
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]

            def carries(b):
                text = b.get("text") or ""
                if bucket == "refusals":
                    name = (res.get("preferred_provider") or {}).get("asked_for")
                    return bool(REFUSAL_RE.search(text)) or bool(name and name.split(" ")[0] in text)
                return bool(needle) and needle in digits_of(text)

            by_tool = any(j in tool_idx and tool_idx[j][0] == tool and tool_idx[j][1] == res for j, _ in turn_bots)
            by_model_same_turn = any(carries(b) for j, b in turn_bots if j not in tool_idx and j > i)
            later_any = any(carries(b) for j, b in later)
            entry = {"conversation": conv, "tool": tool, "turn": turn,
                     "what": res.get("provider_acceptance") or res.get("reason") or status,
                     "reference": res.get("assistance_ref") or res.get("desk_ref"),
                     "delivered_same_turn": by_tool or by_model_same_turn,
                     "by_tool_message": by_tool, "by_model_same_turn": by_model_same_turn,
                     "delivered_at_all": by_tool or later_any}
            report[bucket].append(entry)
        for u in [x for x in events if x.get("event") == "user" and not str(x.get("text") or "").startswith("/")]:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    vals = report["answer_wait_ms"]
    report["answer_wait_ms"] = {"n": len(vals), "p50": pct(vals, 0.5), "p95": pct(vals, 0.95),
                                "max": max(vals) if vals else None,
                                "mean": round(statistics.mean(vals), 1) if vals else None}
    return report


def main() -> int:
    run = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_RUN
    report = analyse(run)
    (run / "case-metric.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"{run.name}: case metric {len(report['dispatches_unconfirmed_location'])} dispatches using an "
          f"unconfirmed incident location, of {report['assistance_requests']} assistance requests "
          f"({report['dispatches']} jobs sent to a provider)")
    print(f"  dispatches not where the script's vehicle is: {len(report['dispatches_not_where_the_vehicle_is'])}")
    for reason, convs in sorted(report["blocked"].items()):
        print(f"  blocked {reason}: {len(convs)} ({', '.join(convs)})")
    for key in ("receipts", "refusals", "desk_refs"):
        items = report[key]
        print(f"  {key}: {len(items)}, heard in the same turn {sum(i['delivered_same_turn'] for i in items)}, "
              f"by the tool's message {sum(i['by_tool_message'] for i in items)}, by the model in the same turn "
              f"{sum(i['by_model_same_turn'] for i in items)}, at all {sum(i['delivered_at_all'] for i in items)}")
        for i in items:
            if not i["delivered_same_turn"]:
                print(f"    not in its turn: {i['conversation']} {i['tool']} {i['what']}")
    print(f"  tool messages sent: {report['tool_messages']}")
    print(f"  invented arrival estimates: {len(report['invented_estimates'])}")
    for m in report["invented_estimates"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['text']}")
    print(f"  'on the way' before a provider accepted: {len(report['on_the_way_before_acceptance'])}")
    for m in report["on_the_way_before_acceptance"]:
        print(f"    {m['conversation']} turn {m['turn']}: {m['sentence']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
