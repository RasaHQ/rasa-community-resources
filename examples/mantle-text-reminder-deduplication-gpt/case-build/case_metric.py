#!/usr/bin/env python3
"""The case metric, receipt delivery and unbacked send claims for a recorded run, from its trackers. Stdlib only.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): obsolete or duplicate reminders, divided by queued
reminder attempts.

- Queued reminder attempts: every entry in the `attempts` list of every
  send_appointment_reminder result, in every conversation of the run. A
  suppression counts as an attempt (the reminder was queued), and so does a
  rejected text.
- Obsolete: an attempt that reached the phone (outcome `delivered` or
  `delivered_unacknowledged`) for a revision that was not the booking's
  current revision at delivery.
- Duplicate: an attempt that reached the phone for a revision that already
  had a delivery, either on the ledger before the attempt
  (`prior_deliveries_for_revision`) or earlier in the same conversation.

Receipt delivery: for each reminder that reached the phone, did a bot message
carrying its reference reach the patient in the same turn, and who wrote it:
the tool (its own message, recorded just before its tool_executed event) or
the model. The same for attendance confirmations and change-request
references. Turns where the model closed the skill (complete_skill) after an
outcome without giving the reference itself are listed as silent
completions.

The words, per bot message (Mantle's verbatim responses and the tools' own
messages excluded): sentences saying a reminder was sent now
(lib.reminders.sent_claims, straight and typographic apostrophes), and
whether a tool delivered a reminder in that same turn. A claim with no
delivery in its turn is unbacked.

Also: the wait for the answer, tracker time from each patient message to the
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

from lib import reminders as cc  # noqa: E402

REACHED = ("delivered", "delivered_unacknowledged")

# SMS encoding (GSM 03.38). A text part whose every character is in the GSM-7
# basic set (extension characters count twice) fits 160 characters in one
# segment and 153 per segment when split; any other character forces UCS-2,
# 70 and 67. Computed from the recorded text only: nothing here went through
# Twilio.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = set("^{}\\[~]|€\f")
# The substitutions a sender would make to stay in GSM-7.
PLAIN_SUBSTITUTES = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "\u00a0": " "}


def sms_parts(text: str) -> list[str]:
    """How Rasa 3.21's twilio channel sends a bot message: split on blank lines, one SMS each."""
    return [part for part in (text or "").strip().split("\n\n")]


def sms_segments(part: str) -> tuple[str, int, list[str]]:
    """(encoding, segments, characters outside GSM-7) for one SMS body."""
    outside = sorted({ch for ch in part if ch not in GSM7_BASIC and ch not in GSM7_EXTENSION})
    if outside:
        units = len(part.encode("utf-16-le")) // 2
        return "UCS-2", 1 if units <= 70 else -(-units // 67), outside
    septets = sum(2 if ch in GSM7_EXTENSION else 1 for ch in part)
    return "GSM-7", 1 if septets <= 160 else -(-septets // 153), []


def plain_sms(text: str) -> str:
    return "".join(PLAIN_SUBSTITUTES.get(ch, ch) for ch in text)


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
    """Tracker events with the patient turn each followed (0 = first patient message)."""
    turn, out = -1, []
    for e in tracker.get("events", []):
        if e.get("event") == "user" and not str(e.get("text") or "").startswith("/"):
            turn += 1
        out.append({**e, "_turn": turn})
    return out


def is_tool_message(events: list[dict], i: int) -> bool:
    """Whether bot event i is the message the next tool result produces."""
    for e in events[i + 1:]:
        kind = e.get("event")
        if kind in ("user", "bot"):
            return False
        if kind == "tool_executed":
            expected = cc.customer_receipt(e.get("tool_name"), _result(e.get("result")))
            return expected is not None and expected == events[i].get("text")
    return False


def analyse(run: Path) -> dict:
    report = {"run": run.name, "queued_attempts": [], "obsolete": [], "duplicate": [], "reminders_reached": [],
              "other_refs": [], "silent_completions": [], "sent_claims": [], "unbacked_sent_claims": [],
              "tool_messages": 0, "answer_wait_ms": [],
              "sms": {"bot_messages": 0, "parts": 0, "multi_part_messages": 0, "segments": 0,
                      "segments_if_plain": 0, "ucs2_parts": 0, "ucs2_parts_if_plain": 0, "ucs2_characters": {},
                      "by_writer": {"model": {"parts": 0, "segments": 0, "segments_if_plain": 0, "ucs2_parts": 0},
                                    "tool": {"parts": 0, "segments": 0, "segments_if_plain": 0, "ucs2_parts": 0},
                                    "response": {"parts": 0, "segments": 0, "segments_if_plain": 0,
                                                 "ucs2_parts": 0}}}}
    for path in sorted((run / "trackers").glob("*.json")):
        conv = path.stem
        events = walk(json.loads(path.read_text()))
        tool_msgs: set[int] = set()
        reached: dict[tuple[str, int], int] = {}
        delivered_turns: set[int] = set()
        for i, e in enumerate(events):
            if e.get("event") == "bot" and is_tool_message(events, i):
                tool_msgs.add(i)
        report["tool_messages"] += len(tool_msgs)
        for i, e in enumerate(events):
            if e.get("event") != "tool_executed":
                continue
            tool, res = e.get("tool_name"), _result(e.get("result"))
            if tool == "send_appointment_reminder":
                for a in res.get("attempts") or []:
                    item = {"conversation": conv, "turn": e["_turn"], **a}
                    report["queued_attempts"].append(item)
                    if a.get("outcome") not in REACHED:
                        continue
                    key = (a.get("appointment_id"), a.get("revision"))
                    delivered_turns.add(e["_turn"])
                    if a.get("revision") != a.get("current_revision_at_delivery"):
                        report["obsolete"].append(item)
                    if (a.get("prior_deliveries_for_revision") or 0) > 0 or reached.get(key, 0) > 0:
                        report["duplicate"].append(item)
                    reached[key] = reached.get(key, 0) + 1
            ref, bucket = None, None
            if tool == "send_appointment_reminder" and res.get("delivery") in ("delivered", "unknown") \
                    and any(a.get("outcome") in REACHED for a in res.get("attempts") or []):
                ref, bucket = res.get("reminder_ref"), "reminders_reached"
            elif tool == "record_reminder_reply" and res.get("status") == "confirmed" and not res.get("replay"):
                ref, bucket = res.get("reminder_ref"), "other_refs"
            elif tool == "request_appointment_change" and res.get("status") == "routed" and not res.get("replay"):
                ref, bucket = res.get("change_ref"), "other_refs"
            if not ref:
                continue
            turn = e["_turn"]
            turn_bots = [(j, b) for j, b in enumerate(events) if b.get("event") == "bot" and b["_turn"] == turn]
            carrying = [j for j, b in turn_bots if ref in (b.get("text") or "")]
            by_model = [j for j in carrying if j not in tool_msgs]
            entry = {"conversation": conv, "tool": tool, "reference": ref, "same_turn": bool(carrying),
                     "by_tool_message": any(j in tool_msgs for j in carrying), "by_model_same_turn": bool(by_model)}
            completes = [x for x in events[i + 1:] if x.get("event") == "tool_executed"
                         and x.get("tool_name") == "complete_skill" and x["_turn"] == turn]
            if completes and not by_model:
                report["silent_completions"].append({"conversation": conv, "reference": ref,
                                                     "last_bot": turn_bots[-1][1].get("text") if turn_bots else None})
            report[bucket].append(entry)
        sms = report["sms"]
        for i, e in enumerate(events):
            if e.get("event") != "bot":
                continue
            meta = e.get("metadata") or {}
            writer = "tool" if i in tool_msgs else ("response" if meta.get("utter_action") else "model")
            parts = sms_parts(e.get("text") or "")
            sms["bot_messages"] += 1
            sms["parts"] += len(parts)
            sms["multi_part_messages"] += len(parts) > 1
            for part in parts:
                encoding, segments, outside = sms_segments(part)
                _, plain_segments, plain_outside = sms_segments(plain_sms(part))
                sms["segments"] += segments
                sms["segments_if_plain"] += plain_segments
                sms["ucs2_parts"] += encoding == "UCS-2"
                sms["ucs2_parts_if_plain"] += bool(plain_outside)
                for ch in outside:
                    sms["ucs2_characters"][ch] = sms["ucs2_characters"].get(ch, 0) + 1
                w = sms["by_writer"][writer]
                w["parts"] += 1
                w["segments"] += segments
                w["segments_if_plain"] += plain_segments
                w["ucs2_parts"] += encoding == "UCS-2"
        for i, e in enumerate(events):
            if e.get("event") != "bot" or i in tool_msgs:
                continue
            if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                continue
            hits = cc.sent_claims(e.get("text") or "")
            if hits:
                item = {"conversation": conv, "turn": e["_turn"], "hits": hits, "text": e.get("text"),
                        "delivery_in_turn": e["_turn"] in delivered_turns}
                report["sent_claims"].append(item)
                if not item["delivery_in_turn"]:
                    report["unbacked_sent_claims"].append(item)
        users = [e for e in events if e.get("event") == "user" and not str(e.get("text") or "").startswith("/")]
        for u in users:
            bots = [b for b in events if b.get("event") == "bot" and b["_turn"] == u["_turn"] and b.get("timestamp")]
            if bots and u.get("timestamp"):
                report["answer_wait_ms"].append(round((bots[-1]["timestamp"] - u["timestamp"]) * 1000, 1))
    vals = report["answer_wait_ms"]
    report["answer_wait_ms"] = {"n": len(vals), "p50": pct(vals, 0.5), "p95": pct(vals, 0.95),
                                "max": max(vals) if vals else None,
                                "mean": round(statistics.mean(vals), 1) if vals else None}
    n = len(report["queued_attempts"])
    bad = len({(x["conversation"], x["turn"], x["reminder_ref"]) for x in report["obsolete"] + report["duplicate"]})
    report["case_metric"] = {"obsolete_or_duplicate": bad, "queued_attempts": n,
                             "rate": round(bad / n, 4) if n else None}
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1]).resolve()
    report = analyse(run)
    (run / "case-metric.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    m = report["case_metric"]
    print(f"{run.name}: case metric {m['obsolete_or_duplicate']} obsolete or duplicate of {m['queued_attempts']} "
          "queued reminder attempts")
    outcomes: dict[str, int] = {}
    for a in report["queued_attempts"]:
        outcomes[a["outcome"]] = outcomes.get(a["outcome"], 0) + 1
    print(f"  attempt outcomes: {outcomes}")
    for key in ("obsolete", "duplicate"):
        for x in report[key]:
            print(f"    {key}: {x['conversation']} {x['reminder_ref']} revision {x['revision']}")
    items = report["reminders_reached"]
    print(f"  reminders that reached the phone: {len(items)}, reference shown in the same turn "
          f"{sum(i['same_turn'] for i in items)}, by the tool's message {sum(i['by_tool_message'] for i in items)}, "
          f"by the model {sum(i['by_model_same_turn'] for i in items)}")
    other = report["other_refs"]
    print(f"  attendance and change references: {len(other)}, same turn {sum(i['same_turn'] for i in other)}, "
          f"by the model {sum(i['by_model_same_turn'] for i in other)}")
    print(f"  silent completions after an outcome: {len(report['silent_completions'])}")
    print(f"  sent claims in bot text: {len(report['sent_claims'])}, with no delivery in their turn: "
          f"{len(report['unbacked_sent_claims'])}")
    for c in report["unbacked_sent_claims"]:
        print(f"    {c['conversation']} turn {c['turn']}: {c['hits']}")
    print(f"  tool messages sent: {report['tool_messages']}")
    sms = report["sms"]
    print(f"  as Twilio SMS (computed, not sent): {sms['bot_messages']} bot messages -> {sms['parts']} SMS "
          f"({sms['multi_part_messages']} messages split on blank lines), {sms['segments']} segments; "
          f"{sms['ucs2_parts']} parts forced to UCS-2 by {sms['ucs2_characters']}; with plain punctuation "
          f"{sms['segments_if_plain']} segments, {sms['ucs2_parts_if_plain']} UCS-2 parts")
    for writer, w in sms["by_writer"].items():
        print(f"    {writer}: {w['parts']} parts, {w['segments']} segments ({w['segments_if_plain']} if plain), "
              f"{w['ucs2_parts']} UCS-2")
    print(f"  answer_wait_ms: {report['answer_wait_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
