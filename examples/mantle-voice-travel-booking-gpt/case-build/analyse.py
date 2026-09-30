#!/usr/bin/env python3
"""Case metric, receipt delivery, unheard turns and latency for a stored run. No model, no network.

    python3 case-build/analyse.py <run label> [<run label> ...]

Reads `case-build/results/<label>/results.json` and its trackers, and writes
`analysis.json` next to them. Everything is counted from the tracker and the
harness's own records; nothing here decides pass or fail.

- The case metric: segment changes leaving unresolved dependent services
  unreported, divided by linked-journey changes. A linked-journey change is an
  `apply_journey_change` call that changed the booking (`effects` 1). It
  leaves a service unresolved when its result is `pending` (a service still
  points at the old times). It is reported when a bot message in the same
  caller turn is exactly the tool's receipt, which names each unresolved
  service and the travel-desk reference, and no later bot message in the call
  claims everything is updated (the spec's `all_updated_claim`).
- Before and after: for each change, the segment and every linked service's
  identifier before and after, and whether it points at the new times, from
  the tool result.
- Receipts: for each tool result marked `receipt_sent_to_caller`, whether a
  bot message with exactly that receipt follows in the same caller turn, and
  whether a later model message in that turn restates the change or desk
  reference.
- Unheard turns, counted apart from agent failures: caller turns that
  produced no user event (speech-to-text heard nothing), caller turns whose
  wait reached the 30 s silence timeout, caller turns split into more than one
  user event, and bot turns the caller never heard
  (`voice_channel.audio_missing`).
- Latency: end of caller speech to first bot audio, and the parts Rasa
  reports on the first end marker (processing, TTS first byte); the rest,
  first audio minus those two, is time before Rasa had a transcript plus
  transport. Mantle's `latency_breakdown` gives the model's time to first
  token.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import journeys as hj  # noqa: E402

RESULTS = PROJECT / "case-build" / "results"
SILENCE_TIMEOUT_MS = 30_000  # integrations.yml: silence_timeout: 30


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile, the harness's method, so the figures match summary.md."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(-(-q * 100 * len(ordered) // 100)))
    return round(ordered[min(rank, len(ordered)) - 1], 1)


def dist(values: list[float]) -> dict:
    return {"n": len(values), "p50": pct(values, 0.5), "p95": pct(values, 0.95),
            "max": round(max(values), 1) if values else None}


def parse(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def claim_hits(metric: dict, text: str) -> list[str]:
    pattern = re.compile(metric["pattern"], re.IGNORECASE)
    hedge = re.compile(metric["unless_before"], re.IGNORECASE) if metric.get("unless_before") else None
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        for match in pattern.finditer(sentence):
            if hedge is None or not hedge.search(sentence[: match.start()]):
                hits.append(match.group(0))
    return hits


def changes(tracker: dict, claim_metric: dict) -> list[dict]:
    """Each apply_journey_change call, with its receipt delivery and what the model said after it."""
    events = tracker.get("events", [])
    out = []
    for i, event in enumerate(events):
        if event.get("event") != "tool_executed" or event.get("tool_name") != "apply_journey_change":
            continue
        result = parse(event.get("result"))
        # The engine's confirmation gate logs its own events under the tool's name ("awaiting_confirmation",
        # "declined", or an error for a second call in the turn); only a real execution carries effects.
        if not isinstance(result, dict) or "effects" not in result:
            continue
        start = max((j for j in range(i) if events[j].get("event") == "user"), default=0)
        end = next((j for j in range(i + 1, len(events)) if events[j].get("event") == "user"), len(events))
        turn_bots = [e for e in events[start:end] if e.get("event") == "bot"]
        expected = (hj.customer_receipt("apply_journey_change", result) or "").strip()
        delivered = [b for b in turn_bots if expected and (b.get("text") or "").strip() == expected]
        later_bots = [e for e in events[i + 1:] if e.get("event") == "bot" and e not in delivered]
        claims = [h for b in later_bots for h in claim_hits(claim_metric, b.get("text") or "")]
        refs = [digits(result.get(k) or "") for k in ("change_reference", "desk_reference") if result.get(k)]
        after = False
        restated = 0
        for b in turn_bots:
            if b in delivered:
                after = True
                continue
            if after and any(r and r in digits(b.get("text") or "") for r in refs):
                restated += 1
        unresolved = [r["service"] for r in result.get("linked_services", []) if not r.get("points_at_new_times")]
        out.append({
            "status": result.get("status"), "reason": result.get("reason"), "effects": result.get("effects"),
            "booking": result.get("booking"),
            "segment": result.get("segment"),
            "before_after": [{k: r.get(k) for k in ("service", "state", "before", "after", "points_at_new_times")}
                             for r in result.get("linked_services", [])],
            "unresolved": unresolved,
            "receipt_sent": bool(result.get("receipt_sent_to_caller")),
            "receipt_delivered_in_turn": bool(delivered),
            "receipt_characters": len(expected) if expected else None,
            "model_messages_after_receipt_in_turn":
                sum(1 for b in turn_bots[turn_bots.index(delivered[0]) + 1:]) if delivered else None,
            "reference_restated_by_model": restated,
            "all_updated_claims_after": claims,
        })
    return out


def analyse(label: str) -> dict:
    run = RESULTS / label
    results = json.loads((run / "results.json").read_text())
    spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
    claim_metric = spec["bot_text_metrics"]["all_updated_claim"]

    convs, lat, proc, ttfb, rest, ttft = [], [], [], [], [], []
    totals = {"spoken_turns": 0, "heard_nothing": 0, "silence_timeout_waits": 0, "split": 0, "audio_missing": 0,
              "tool_timeouts": 0, "rime_reconnects": 0, "response_delivery_failed": 0,
              "unrecorded_after_driver_error": 0, "bare_yes": 0, "bare_yes_heard": 0}
    all_changes = []
    for c in results["conversations"]:
        tracker_path = run / "trackers" / f"{c['id']}.json"
        tracker = json.loads(tracker_path.read_text()) if tracker_path.is_file() else {"events": []}
        rows = changes(tracker, claim_metric)
        all_changes += [{**r, "conversation": c["id"]} for r in rows]
        asr = ((c.get("voice") or {}).get("asr")) or []
        heard_nothing = [a["intended"] for a in asr if a.get("user_events") == 0]
        waits = [t["user"] for t in c.get("turns", [])
                 if (t.get("extra") or {}).get("mode") == "audio" and (t.get("latency_ms") or 0) >= SILENCE_TIMEOUT_MS]
        counts = c.get("log_events") or {}
        # A driver timeout ends the call before the turn is recorded: the scripted lines after the last
        # recorded turn were never answered. The first of them was streamed; the tracker says whether it
        # became a user event.
        script = next((s["turns"] for s in spec["conversations"] if s["id"] == c["id"]), [])
        unrecorded = [t["user"] for t in script[len(c.get("turns", [])):]] if c.get("error") else []
        tracker_users = [e.get("text") for e in tracker.get("events", [])
                         if e.get("event") == "user" and not (e.get("text") or "").startswith("/")]
        lost_at_timeout = (unrecorded[:1] if unrecorded and len(tracker_users) <= len(c.get("turns", []))
                           else [])
        heard_nothing += lost_at_timeout
        totals["unrecorded_after_driver_error"] += len(unrecorded)
        totals["spoken_turns"] += len(asr) + len(lost_at_timeout)
        totals["heard_nothing"] += len(heard_nothing)
        bare_yes = [(a["intended"], a.get("user_events", 0) > 0) for a in asr if a["intended"].strip() in ("Yes.", "yes")]
        bare_yes += [(t, False) for t in lost_at_timeout if t.strip() == "Yes."]
        totals["bare_yes"] += len(bare_yes)
        totals["bare_yes_heard"] += sum(1 for _, ok in bare_yes if ok)
        totals["silence_timeout_waits"] += len(waits)
        totals["split"] += sum(1 for a in asr if (a.get("user_events") or 0) > 1)
        totals["audio_missing"] += counts.get("voice_channel.audio_missing", 0)
        totals["tool_timeouts"] += counts.get("mantle.skill_executor.tool.timeout", 0)
        totals["rime_reconnects"] += counts.get("horizon.rime_idle_reconnect", 0)
        totals["response_delivery_failed"] += counts.get("output_channel.response_delivery_failed", 0)
        for turn in c.get("turns", []):
            extra = turn.get("extra") or {}
            first = extra.get("eos_to_first_audible_ms") or extra.get("eos_to_first_audio_ms")
            for b in extra.get("latency_breakdown") or []:
                v = ((b.get("first_agent_response") or {}).get("llm_time_to_first_token_ms")
                     if isinstance(b, dict) else None)
                if v is not None:
                    ttft.append(v)
            if first is None:
                continue
            lat.append(first)
            markers = extra.get("end_markers") or []
            if markers:
                p = markers[0].get("rasa_processing_latency_ms")
                f = markers[0].get("tts_first_byte_latency_ms")
                if p is not None and f is not None:
                    proc.append(p)
                    ttfb.append(f)
                    rest.append(first - p - f)
        convs.append({"id": c["id"], "kind": c.get("kind"), "outcome": c.get("outcome"),
                      "heard_nothing": heard_nothing, "silence_timeout_waits": waits, "changes": rows})

    linked = [r for r in all_changes if r["effects"] == 1]
    with_unresolved = [r for r in linked if r["unresolved"]]
    unreported = [r for r in with_unresolved
                  if not r["receipt_delivered_in_turn"] or r["all_updated_claims_after"]]
    outcome_by_kind: dict[str, dict] = {}
    for c in convs:
        k = outcome_by_kind.setdefault(c["kind"], {"pass": 0, "fail": 0, "provider_error": 0, "skipped": 0})
        k[c["outcome"] if c["outcome"] in k else "fail"] += 1
    sent = [r for r in all_changes if r["receipt_sent"]]
    report = {
        "run": label,
        "conversations": len(convs),
        "outcomes": outcome_by_kind,
        "case_metric": {
            "metric": "segment changes leaving unresolved dependent services unreported / linked-journey changes",
            "unreported": len(unreported),
            "linked_journey_changes": len(linked),
            "changes_with_unresolved_services": len(with_unresolved),
            "blocked_before_any_change": sum(1 for r in all_changes if r["effects"] == 0),
            "by_status": {s: sum(1 for r in all_changes if r["status"] == s)
                          for s in sorted({str(r["status"]) for r in all_changes})},
        },
        "receipts": {
            "sent_by_tool": len(sent),
            "delivered_in_turn": sum(1 for r in sent if r["receipt_delivered_in_turn"]),
            "reference_restated_by_model": sum(1 for r in sent if r["reference_restated_by_model"]),
            "characters": dist([r["receipt_characters"] for r in sent if r["receipt_characters"]]),
        },
        "unheard": {"spoken_caller_turns": totals["spoken_turns"],
                    "caller_turns_heard_as_nothing": totals["heard_nothing"],
                    "caller_turns_waiting_for_silence_timeout": totals["silence_timeout_waits"],
                    "caller_turns_split": totals["split"],
                    "bare_yes_turns": totals["bare_yes"], "bare_yes_heard": totals["bare_yes_heard"],
                    "scripted_lines_unrecorded_after_driver_error": totals["unrecorded_after_driver_error"],
                    "bot_turns_audio_missing": totals["audio_missing"]},
        "engine_events": {"tool_timeouts": totals["tool_timeouts"], "rime_idle_reconnects": totals["rime_reconnects"],
                          "response_delivery_failed": totals["response_delivery_failed"]},
        "latency_ms": {"eos_to_first_audio": dist(lat), "rasa_processing": dist(proc),
                       "tts_first_byte": dist(ttfb), "remainder_before_transcript_and_transport": dist(rest),
                       "llm_time_to_first_token": dist(ttft)},
        "by_conversation": convs,
    }
    (run / "analysis.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for label in sys.argv[1:]:
        report = analyse(label)
        print(json.dumps({k: v for k, v in report.items() if k != "by_conversation"}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
