#!/usr/bin/env python3
"""Card-data scan, receipt delivery, unheard turns and latency for a stored run. No model, no network.

    python3 case-build/analyse.py <run label> [<run label> ...]

Reads `case-build/results/<label>/results.json` and its trackers, and writes
`analysis.json` next to them. Everything is counted from the tracker and the
harness's own records; nothing here decides pass or fail.

- Card data in the conversation record. Every user text, bot text, tool
  argument, tool result string and memory value in each tracker is scanned
  with `lib.pci` for anything it would remove (8+ digit runs, codes after a
  card cue). For conversations whose spec lists `secrets`, the digits of each
  secret are also looked for in the digits of every such string. The
  casebook metric is conversation records holding payment secrets divided by
  payment-assisted sessions (a payment tool ran, or the caller read card
  details). The server's `willowshop.model_request_scan` lines say whether
  card digits reached a model request. The raw server log (kept out of git)
  is searched for the 16-digit test numbers when it is present.
- Receipts. For each tool result marked `receipt_sent_to_caller`, whether a
  bot message with exactly that receipt follows in the same caller turn, and
  whether a later model message in that turn restates its processor
  reference or order number.
- Unheard turns: caller turns that produced no user event (speech-to-text
  heard nothing), apart from agent failures; and bot turns the caller never
  heard (`voice_channel.audio_missing`).
- Latency: end of caller speech to first bot audio, and the parts Rasa
  reports on the first end marker (processing, TTS first byte); the rest,
  first audio minus those two, is time before Rasa had a transcript plus
  transport.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import payments as wp  # noqa: E402
from lib import pci  # noqa: E402

RESULTS = PROJECT / "case-build" / "results"
# Runs recorded before hooks.py masked the date-time in Mantle's system prompt
# ("Current date and time: 2026-09-30 19:37" reads as a 12-digit run), so their
# model-request scan flagged every request. Their scan counts are not reported.
SCAN_COUNTED_PROMPT_DATETIME = {"estimate", "2026-09-30-gpt-5.5-low"}
PAYMENT_TOOLS = {"look_up_order_balance", "prepare_secure_payment", "send_secure_payment_link",
                 "check_payment_status", "leave_payment_pending"}
SKIP_KEYS = {"timestamp", "time", "sender_id", "conversation_id", "model_id", "session_id", "id", "message_id",
             "turn_id", "metadata", "input_channel", "parse_data"}


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


def strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if k not in SKIP_KEYS:
                yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def record_strings(tracker: dict) -> list[tuple[str, str]]:
    """(where, text) for what the conversation record holds that a person or model said or a tool stored."""
    out = []
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind in ("user", "bot") and event.get("text"):
            out.append((kind, event["text"]))
        elif kind == "tool_executed":
            for s in strings(event.get("arguments") or {}):
                out.append(("tool_argument", s))
            for s in strings(parse(event.get("result"))):
                out.append(("tool_result", s))
        elif kind in ("memory_set", "slot"):
            for s in strings(event.get("value")):
                out.append((kind, s))
    for s in strings(tracker.get("slots") or {}):
        out.append(("slot_state", s))
    return out


def scan_record(tracker: dict, secrets: list[str]) -> dict:
    # The harness's conversation id ends in a run-date stamp (8 digits); it is not card data.
    own_id = tracker.get("sender_id") or ""
    found = [(where, text) for where, text in record_strings(tracker)
             if pci.contains_payment_secret(text.replace(own_id, "") if own_id else text)]
    hits = {}
    for secret in secrets:
        places = sorted({where for where, text in record_strings(tracker) if secret in pci.digits_only(text)})
        if places:
            hits[secret] = places
    placeholders = sum(1 for where, text in record_strings(tracker) if where == "user" and pci.PLACEHOLDER in text)
    return {"strings_with_card_details": len(found), "where": sorted({w for w, _ in found}),
            "listed_secrets_found": hits, "user_turns_with_placeholder": placeholders}


def receipts(tracker: dict) -> list[dict]:
    """Each tool-sent receipt: delivered in its turn, and restated by the model after it."""
    events = tracker.get("events", [])
    out = []
    for i, event in enumerate(events):
        if event.get("event") != "tool_executed":
            continue
        result = parse(event.get("result"))
        if not isinstance(result, dict) or not result.get("receipt_sent_to_caller"):
            continue
        if event.get("tool_name") == "resolve_tool_confirmation":
            continue  # the engine's copy of the confirmed tool's result, counted under that tool
        tool = event.get("tool_name")
        expected = wp.customer_receipt(tool, result)
        # Bot messages in this caller turn: from the last user event before the tool to the next one.
        start = max((j for j in range(i) if events[j].get("event") == "user"), default=0)
        end = next((j for j in range(i + 1, len(events)) if events[j].get("event") == "user"), len(events))
        turn_bots = [e for e in events[start:end] if e.get("event") == "bot"]
        delivered = [b for b in turn_bots if (b.get("text") or "").strip() == (expected or "").strip()]
        reference = result.get("processor_reference") or ""
        marks = [pci.digits_only(reference)] if reference else []
        order_digits = pci.digits_only(result.get("order") or "")
        restated_reference, restated_order = 0, 0
        after = False
        for b in turn_bots:
            if b in delivered:
                after = True
                continue
            if not after:
                continue
            digits = pci.digits_only(b.get("text") or "")
            if any(m and m in digits for m in marks):
                restated_reference += 1
            if order_digits and order_digits in digits:
                restated_order += 1
        out.append({"tool": tool, "status": result.get("status"), "reason": result.get("reason"),
                    "delivered": bool(delivered),
                    "model_messages_after": sum(1 for b in turn_bots[turn_bots.index(delivered[0]) + 1:])
                    if delivered else None,
                    "restated_reference": restated_reference, "restated_order": restated_order,
                    "has_reference": bool(reference)})
    return out


def analyse(label: str) -> dict:
    run = RESULTS / label
    results = json.loads((run / "results.json").read_text())
    spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
    secrets_by_id = {c["id"]: c.get("secrets", []) for c in spec["conversations"]}
    raw_logs = sorted((RESULTS / "raw").glob("*/server.log")) if (RESULTS / "raw").is_dir() else []

    convs, lat, proc, ttfb, rest = [], [], [], [], []
    totals = {"payment_assisted": 0, "records_with_secrets": 0, "unheard_caller_turns": 0, "spoken_turns": 0,
              "split_caller_turns": 0, "audio_missing": 0, "model_requests": 0,
              "model_request_messages_with_card_details": 0, "model_requests_with_placeholder": 0,
              "incoming_message_hook": 0, "outgoing_text_hook": 0, "turn_started_hook": 0}
    all_receipts = []
    for c in results["conversations"]:
        tracker_path = run / "trackers" / f"{c['id']}.json"
        tracker = json.loads(tracker_path.read_text()) if tracker_path.is_file() else {"events": []}
        secrets = secrets_by_id.get(c["id"], [])
        scan = scan_record(tracker, secrets)
        tools = {t["tool"] for t in c.get("tool_calls", [])}
        assisted = bool(tools & PAYMENT_TOOLS) or bool(secrets)
        holds = scan["strings_with_card_details"] > 0 or bool(scan["listed_secrets_found"])
        totals["payment_assisted"] += assisted
        totals["records_with_secrets"] += assisted and holds
        asr = ((c.get("voice") or {}).get("asr")) or []
        unheard = [a["intended"] for a in asr if a.get("user_events") == 0]
        totals["unheard_caller_turns"] += len(unheard)
        totals["spoken_turns"] += len(asr)
        totals["split_caller_turns"] += sum(1 for a in asr if (a.get("user_events") or 0) > 1)
        details = c.get("log_event_details") or {}
        counts = c.get("log_events") or {}
        totals["audio_missing"] += counts.get("voice_channel.audio_missing", 0)
        scans = details.get("willowshop.model_request_scan") or []
        totals["model_requests"] += len(scans)
        totals["model_request_messages_with_card_details"] += sum(s.get("messages_with_card_details", 0) for s in scans)
        totals["model_requests_with_placeholder"] += sum(1 for s in scans if s.get("messages_with_placeholder"))
        for name in ("incoming_message_hook", "outgoing_text_hook", "turn_started_hook"):
            totals[name] += counts.get(f"willowshop.{name}", 0)
        rec = receipts(tracker)
        all_receipts += [{**r, "conversation": c["id"]} for r in rec]
        for turn in c.get("turns", []):
            extra = turn.get("extra") or {}
            first = extra.get("eos_to_first_audible_ms") or extra.get("eos_to_first_audio_ms")
            markers = extra.get("end_markers") or []
            if first is None:
                continue
            lat.append(first)
            if markers:
                p = markers[0].get("rasa_processing_latency_ms")
                f = markers[0].get("tts_first_byte_latency_ms")
                if p is not None and f is not None:
                    proc.append(p)
                    ttfb.append(f)
                    rest.append(first - p - f)
        convs.append({"id": c["id"], "kind": c.get("kind"), "outcome": c.get("outcome"),
                      "payment_assisted": assisted, "record_holds_card_details": holds, "scan": scan,
                      "unheard_caller_turns": unheard,
                      "model_request_messages_with_card_details":
                          None if label in SCAN_COUNTED_PROMPT_DATETIME
                          else sum(s.get("messages_with_card_details", 0) for s in scans),
                      "receipts": rec})

    log_hits = {}
    for log in raw_logs:
        text = log.read_text(errors="replace")
        for secret in {s for c in spec["conversations"] for s in c.get("secrets", []) if len(s) >= 16}:
            n = sum(1 for line in text.splitlines() if secret in pci.digits_only(line))
            if n:
                log_hits.setdefault(log.parent.name, {})[secret] = n

    outcome_by_kind: dict[str, dict] = {}
    for c in convs:
        k = outcome_by_kind.setdefault(c["kind"], {"pass": 0, "fail": 0, "provider_error": 0, "skipped": 0})
        k[c["outcome"] if c["outcome"] in k else "fail"] += 1
    delivered = [r for r in all_receipts if r["delivered"]]
    report = {
        "run": label,
        "conversations": len(convs),
        "outcomes": outcome_by_kind,
        "card_data": {
            "metric": "conversation records containing payment secrets / payment-assisted sessions",
            "records_with_secrets": totals["records_with_secrets"],
            "payment_assisted_sessions": totals["payment_assisted"],
            "caller_turns_with_card_details_removed": sum(c["scan"]["user_turns_with_placeholder"] for c in convs),
            "model_requests": totals["model_requests"],
            "model_request_messages_with_card_details": None if label in SCAN_COUNTED_PROMPT_DATETIME
            else totals["model_request_messages_with_card_details"],
            "model_requests_carrying_placeholder": totals["model_requests_with_placeholder"],
            **({"model_request_scan_note": "recorded before hooks.py masked the prompt's date-time, which the "
                                           "scan counted as card digits in every request; see "
                                           "2026-09-30-model-request-rescan"}
               if label in SCAN_COUNTED_PROMPT_DATETIME else {}),
            "raw_server_log_lines_with_test_card_numbers": log_hits,
            "raw_server_logs_scanned": [p.parent.name for p in raw_logs],
        },
        "hooks": {k: totals[k] for k in ("turn_started_hook", "incoming_message_hook", "outgoing_text_hook")},
        "receipts": {
            "sent_by_tools": len(all_receipts),
            "delivered_in_turn": len(delivered),
            "by_tool": {t: sum(1 for r in all_receipts if r["tool"] == t) for t in sorted({r["tool"] for r in all_receipts})},
            "with_processor_reference": sum(1 for r in all_receipts if r["has_reference"]),
            "reference_restated_by_model": sum(1 for r in all_receipts if r["restated_reference"]),
            "order_restated_by_model": sum(1 for r in all_receipts if r["restated_order"]),
        },
        "unheard": {"spoken_caller_turns": totals["spoken_turns"],
                    "caller_turns_heard_as_nothing": totals["unheard_caller_turns"],
                    "caller_turns_split": totals["split_caller_turns"],
                    "bot_turns_audio_missing": totals["audio_missing"]},
        "latency_ms": {"eos_to_first_audio": dist(lat), "rasa_processing": dist(proc),
                       "tts_first_byte": dist(ttfb), "remainder_before_transcript_and_transport": dist(rest)},
        "by_conversation": convs,
    }
    (run / "analysis.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for label in sys.argv[1:]:
        report = analyse(label)
        print(json.dumps({k: v for k, v in report.items() if k != "by_conversation"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
