#!/usr/bin/env python3
"""Read-only conversation scorecard. Output contains counts, not caller details.

Usage: python scripts/conversation_quality.py --sender DEMO_ID --server http://localhost:5007
   or: python scripts/conversation_quality.py --tracker exported-tracker.json
Text timestamps are not microphone/TTS latency. Repeated questions are review
candidates: a retry after an unclear answer may be entirely appropriate.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import statistics
import urllib.parse
import urllib.request


def _result(event):
    value = event.get("result") or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def score(tracker: dict) -> dict:
    turns, current = [], None
    saved, corrected_saves = set(), set()
    corrections, summary_seen, correction_pending = 0, False, False
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "user":
            current = {"timestamp": event.get("timestamp"), "bot": [], "times": []}
            turns.append(current)
        elif kind == "bot" and current is not None:
            if not (event.get("metadata") or {}).get("streaming"):
                current["bot"].append(event.get("text") or "")
                current["times"].append(event.get("timestamp"))
        elif kind == "tool_executed":
            name, result = event.get("tool_name"), _result(event)
            if name == "prepare_report_summary" and result.get("ok"):
                summary_seen = True
            if name == "revise_report" and result.get("ok") and summary_seen:
                corrections += 1
                correction_pending = True
            elif name == "capture_report" and result.get("corrected") and summary_seen:
                corrections += 1
                correction_pending = True
            if name in {"file_complaint", "attach_to_existing"} and result.get("ok") and result.get("complaint_id"):
                saved.add(result["complaint_id"])
                if correction_pending:
                    corrected_saves.add(result["complaint_id"])
                correction_pending, summary_seen = False, False

    questions, within_turn_repeats, internal_text, latencies = Counter(), 0, 0, []
    for turn in turns:
        local = Counter()
        for text in turn["bot"]:
            if re.search(r'"(?:target_id|tool_name|arguments)"\s*:|\b\w+__main\b', text):
                internal_text += 1
            for question in re.findall(r"[^.!?]*\?", text):
                normal = re.sub(r"\W+", " ", question.lower()).strip()
                if normal:
                    local[normal] += 1
        within_turn_repeats += sum(count - 1 for count in local.values())
        questions.update(local.keys())
        if turn["times"] and isinstance(turn["timestamp"], (int, float)) and isinstance(turn["times"][0], (int, float)):
            latencies.append(max(0, turn["times"][0] - turn["timestamp"]))
    return {
        "user_turns": len(turns),
        "turns_without_bot_text": sum(not any(t["bot"]) for t in turns),
        "duplicate_questions_within_turn": within_turn_repeats,
        "question_repeat_candidates_across_turns": sum(n - 1 for n in questions.values()),
        "internal_tool_text_messages": internal_text,
        "saved_reports": len(saved),
        "accepted_post_review_corrections": corrections,
        "reports_saved_after_correction": len(corrected_saves),
        "median_time_to_first_bot_text_seconds": round(statistics.median(latencies), 2) if latencies else None,
        "max_time_to_first_bot_text_seconds": round(max(latencies), 2) if latencies else None,
        "notes": [
            "Counts describe this tracker snapshot, not a population success rate.",
            "Question repeats are review candidates, not proof of unnecessary questions.",
            "Saved-after-correction does not prove the corrected value is right; inspect the saved record.",
            "An unfinished turn may have no bot text yet. Text timings include greeting and are not voice latency.",
            "No caller text, phone number, reference or sender ID is included in this scorecard.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tracker", type=Path)
    source.add_argument("--sender")
    parser.add_argument("--server", default="http://localhost:5007")
    args = parser.parse_args()
    if args.tracker:
        with args.tracker.open() as handle:
            tracker = json.load(handle)
    else:
        url = (args.server.rstrip("/") + "/conversations/" +
               urllib.parse.quote(args.sender, safe="") + "/tracker?include_events=ALL")
        with urllib.request.urlopen(url, timeout=30) as response:
            tracker = json.load(response)
    print(json.dumps(score(tracker), indent=2))


if __name__ == "__main__":
    main()
