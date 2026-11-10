#!/usr/bin/env python3
"""The case metric, hold outcomes and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): rebooking confirmations without committed capacity,
divided by accepted recovery offers.

- Accepted recovery offers: the passenger said yes to the engine's question
  for commit_rebooking (``resolve_tool_confirmation`` with ``confirmed: true``
  while commit_rebooking was the pending tool).
- Confirmations without committed capacity: a bot message with a sentence that
  calls the passenger rebooked or confirmed (lib.rebooking.CONFIRMED_CLAIM_PATTERN,
  with its hedge list) when no tool had returned a committed replacement in
  that conversation by then. The tool's own receipt is excluded (it is sent
  from the tool result), and so are verbatim responses. Counted per message
  and per conversation.

Holds, as the casebook's evidence line asks: every hold_recovery_option and
resume_hold outcome, with rejected holds (blocked or unavailable, by reason)
counted apart from abandoned ones (a hold still active when the conversation
ended, never committed or released).

Receipt delivery: for each replacement reference a tool issued
(commit_rebooking succeeded, or check_rebooking_status committed), did a bot
message carry it, in the same passenger turn, and who wrote it: the tool (its
own receipt message) or the model. For each pending commit, did a message in
that turn carry the hold's expiry; for each hold that expired at commit, did
a message say so. The same for desk references. Turns where the model closed
the skill (complete_skill) after a receipt without giving the reference itself
are listed as silent completions.

Also: the wait for the answer, tracker time from each passenger message to
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

from lib import rebooking as rb  # noqa: E402

CLAIM = re.compile(rb.CONFIRMED_CLAIM_PATTERN, re.IGNORECASE)
HEDGE = re.compile(rb.CONFIRMED_HEDGE_PATTERN, re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
HOLD_TOOLS = ("hold_recovery_option", "resume_hold")


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def claim_sentences(text: str) -> list[str]:
    hits = []
    for sentence in SENTENCE.split(text or ""):
        for m in CLAIM.finditer(sentence):
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
            expected = rb.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def analyse(run: Path) -> dict:
    report = {"run": run.name, "accepted_offers": 0, "declined_offers": 0, "commit_attempts": 0,
              "unbacked_confirmation_messages": [], "conversations_with_unbacked_confirmation": [],
              "holds": {"made": 0, "rejected": {}, "released": 0, "expired_at_commit": 0, "committed": 0,
                        "pending": 0, "abandoned": [], "rejected_items": []},
              "replacement_refs": [], "pending_receipts": [], "expired_receipts": [], "desk_refs": [],
              "silent_completions": [], "answer_wait_ms": [], "tool_receipt_messages": 0}
    holds = report["holds"]
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        committed = False
        pending_tool = None
        receipt_idx: set[int] = set()
        live_holds: dict[str, str] = {}  # hold_id -> state
        for i, e in enumerate(events):
            kind = e.get("event")
            if kind == "memory_set" and e.get("key") == "system.pending_tool_confirmation":
                pending_tool = (e.get("value") or {}).get("tool_name")
            if kind == "bot":
                own = is_tool_receipt(events, i)
                if own:
                    receipt_idx.add(i)
                    report["tool_receipt_messages"] += 1
                meta = e.get("metadata") or {}
                if meta.get("mantle_response_source") == "verbatim" or own:
                    continue
                hits = claim_sentences(e.get("text") or "")
                if hits and not committed:
                    report["unbacked_confirmation_messages"].append(
                        {"conversation": conv, "turn": e["_turn"], "sentences": hits})
                    if conv not in report["conversations_with_unbacked_confirmation"]:
                        report["conversations_with_unbacked_confirmation"].append(conv)
                continue
            if kind != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            status, reason = res.get("status"), res.get("reason")
            if tool == "resolve_tool_confirmation" and pending_tool == "commit_rebooking":
                args = e.get("arguments") or {}
                if args.get("confirmed") is True:
                    report["accepted_offers"] += 1
                elif args.get("confirmed") is False:
                    report["declined_offers"] += 1
                pending_tool = None
            if tool in HOLD_TOOLS:
                if status == "held":
                    if tool == "hold_recovery_option":
                        holds["made"] += 1
                    live_holds[res["hold_id"]] = "active"
                elif status in ("blocked", "unavailable"):
                    holds["rejected"][reason] = holds["rejected"].get(reason, 0) + 1
                    holds["rejected_items"].append({"conversation": conv, "tool": tool, "reason": reason,
                                                    "option": res.get("option_id") or res.get("hold_id")})
            if tool == "release_hold" and status == "released":
                holds["released"] += 1
                live_holds[res["hold_id"]] = "released"
            if tool == "commit_rebooking" and status in ("succeeded", "pending", "blocked") and not res.get("replay"):
                report["commit_attempts"] += 1
                hid = res.get("hold_id")
                if status == "succeeded":
                    holds["committed"] += 1
                    live_holds[hid] = "committed"
                elif status == "pending":
                    holds["pending"] += 1
                    live_holds[hid] = "pending"
                elif reason == "hold_expired" and res.get("hold_state") == "expired":
                    holds["expired_at_commit"] += 1
                    live_holds[hid] = "expired"
                elif reason == "unusable_itinerary" and res.get("hold_released"):
                    live_holds[hid] = "released"
            if (tool, status) in (("commit_rebooking", "succeeded"), ("check_rebooking_status", "committed")):
                committed = True
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            later_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and j > i]

            def delivery(ref: str) -> dict:
                carrying = [(j, b) for j, b in turn_bots + later_bots if ref and ref in (b.get("text") or "")]
                model_same = [b for j, b in turn_bots if j not in receipt_idx and ref in (b.get("text") or "")]
                return {"delivered": bool(carrying),
                        "same_turn": any(events[j]["_turn"] == turn for j, _ in carrying),
                        "by_tool_receipt": any(j in receipt_idx for j, _ in carrying if events[j]["_turn"] == turn),
                        "by_model_same_turn": bool(model_same)}

            if (tool, status) in (("commit_rebooking", "succeeded"), ("check_rebooking_status", "committed")) \
                    and not res.get("replay"):
                ref = res.get("replacement_reference")
                if any(r["reference"] == ref and r["conversation"] == conv for r in report["replacement_refs"]):
                    continue
                entry = {"conversation": conv, "tool": tool, "reference": ref, **delivery(ref)}
                completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                             and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
                if completes and not entry["by_model_same_turn"]:
                    report["silent_completions"].append({"conversation": conv, "reference": ref,
                                                         "last_bot": turn_bots[-1][1].get("text") if turn_bots else None})
                report["replacement_refs"].append(entry)
            elif tool == "commit_rebooking" and status == "pending" and not res.get("replay"):
                until = res.get("held_until", "")
                clock = until.split(" ")[0] if until else ""
                report["pending_receipts"].append({"conversation": conv, "commit_reference": res.get("commit_reference"),
                                                   "held_until": until, **delivery(clock)})
            elif tool == "commit_rebooking" and reason == "hold_expired" and res.get("hold_state") == "expired":
                said = [b for j, b in turn_bots if "expire" in (b.get("text") or "").lower()]
                report["expired_receipts"].append({"conversation": conv, "hold_id": res.get("hold_id"),
                                                   "told_same_turn": bool(said),
                                                   "by_tool_receipt": any(j in receipt_idx for j, b in turn_bots
                                                                          if "expire" in (b.get("text") or "").lower())})
            elif tool == "request_recovery_desk" and status == "routed" and not res.get("replay"):
                ref = res.get("desk_reference")
                report["desk_refs"].append({"conversation": conv, "reference": ref, **delivery(ref)})
        for hid, state in live_holds.items():
            if state == "active":
                holds["abandoned"].append({"conversation": conv, "hold_id": hid})
        users = [e for e in events if e.get("event") == "user" and not str(e.get("text") or "").startswith("/")]
        for u in users:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    n = report["accepted_offers"]
    bad = len(report["conversations_with_unbacked_confirmation"])
    report["case_metric"] = {"numerator_conversations": bad, "accepted_offers": n,
                             "value": round(bad / n, 4) if n else None}
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
    m = report["case_metric"]
    print(f"{run.name}: case metric {m['numerator_conversations']} conversation(s) with a confirmation claim before "
          f"committed capacity / {m['accepted_offers']} accepted recovery offers "
          f"({len(report['unbacked_confirmation_messages'])} messages); declined {report['declined_offers']}; "
          f"commit attempts {report['commit_attempts']}")
    for msg in report["unbacked_confirmation_messages"]:
        print(f"    {msg['conversation']} turn {msg['turn']}: {msg['sentences']}")
    h = report["holds"]
    print(f"  holds: made {h['made']}, rejected {sum(h['rejected'].values())} {h['rejected']}, released "
          f"{h['released']}, expired at commit {h['expired_at_commit']}, committed {h['committed']}, pending "
          f"{h['pending']}, abandoned {len(h['abandoned'])}")
    for key, label in (("replacement_refs", "replacement references"), ("desk_refs", "desk references")):
        items = report[key]
        print(f"  {label}: {len(items)} issued, delivered {sum(i['delivered'] for i in items)}, same turn "
              f"{sum(i['same_turn'] for i in items)}, by the tool's receipt {sum(i['by_tool_receipt'] for i in items)}, "
              f"by the model in the same turn {sum(i['by_model_same_turn'] for i in items)}")
    p = report["pending_receipts"]
    print(f"  pending commits: {len(p)}, hold expiry told in the same turn {sum(i['same_turn'] for i in p)} "
          f"(tool {sum(i['by_tool_receipt'] for i in p)}, model {sum(i['by_model_same_turn'] for i in p)})")
    x = report["expired_receipts"]
    print(f"  holds expired at commit: {len(x)}, told in the same turn {sum(i['told_same_turn'] for i in x)}")
    print(f"  silent completions after a receipt: {len(report['silent_completions'])}")
    print(f"  tool receipt messages sent: {report['tool_receipt_messages']}")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
