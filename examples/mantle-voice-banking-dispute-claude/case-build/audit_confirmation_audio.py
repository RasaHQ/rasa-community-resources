"""Inspect saved Northgate voice results, without making provider calls.

This recognises this example's English confirmation question only. Audio in
a turn is not proof that the complete question played or that a human heard it.
Only results.json is read; disagreement with a separate tracker is not detected.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


QUESTION = "Would you like to confirm this transaction?"
MISSING_REASON = "tts_produced_no_audio_without_barge_in"


def audit(report: dict) -> dict:
    rows = []
    unbound_events = []
    for conversation in report["conversations"]:
        events = conversation.get("log_event_details", {}).get(
            "voice_channel.audio_missing", []
        )
        occurrences = Counter(
            text for turn in conversation["turns"]
            for text in turn.get("bot", []) if QUESTION in text
        )

        def binds(event):
            return (
                occurrences.get(event.get("text"), 0) == 1
                and bool(conversation.get("conversation_id"))
                and event.get("conversation_id") == conversation["conversation_id"]
                and event.get("reason") == MISSING_REASON
            )

        for event in events:
            if not binds(event):
                unbound_events.append({
                    "case": conversation["id"],
                    "event": event,
                    "finding": "event_cannot_be_bound_to_one_confirmation",
                })
        for index, turn in enumerate(conversation["turns"], 1):
            questions = [text for text in turn.get("bot", []) if QUESTION in text]
            if not questions:
                continue
            observation = turn.get("extra", {})
            candidates = [event for event in events if event.get("text") in questions]
            matches = [event for event in candidates if binds(event)]
            # These event summaries have no turn index. Repeated identical
            # questions cannot be assigned to one turn from text alone.
            unique_question = len(questions) == 1 and occurrences[questions[0]] == 1
            no_audio = (
                observation.get("bot_audio_s") == 0
                and "eos_to_first_audio_ms" in observation
                and observation["eos_to_first_audio_ms"] is None
                and "eos_to_first_audible_ms" in observation
                and observation["eos_to_first_audible_ms"] is None
                and observation.get("interrupts") == 0
            )
            seconds = observation.get("bot_audio_s")
            has_audio = (
                isinstance(seconds, (int, float)) and seconds > 0
                and observation.get("eos_to_first_audio_ms") is not None
            )
            if len(candidates) == len(matches) == 1 and no_audio and unique_question:
                finding = "missing_audio_corroborated"
            elif candidates:
                finding = "conflicting_or_incomplete_evidence"
            elif has_audio:
                finding = "audio_recorded_in_turn"
            else:
                finding = "delivery_unverified"
            rows.append({
                "case": conversation["id"],
                "conversation_id": conversation.get("conversation_id"),
                "confirmation_turn": index,
                "finding": finding,
                "original_checks_passed": conversation.get("passed"),
                "bot_audio_s": seconds,
                "first_audio_ms": observation.get("eos_to_first_audio_ms"),
                "missing_audio_utterance_ids": [event.get("utterance_id") for event in matches],
            })
    return {
        "confirmations": rows,
        "unbound_events": unbound_events,
        "review_required": bool(unbound_events) or not rows or any(
            row["finding"] != "audio_recorded_in_turn" for row in rows
        ),
        "scope": "Captured turn windows only; audio presence does not prove complete question playback or human hearing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results", type=Path, nargs="?",
        default=Path(__file__).parent / "results/2026-09-29-custom-vocab/results.json",
    )
    args = parser.parse_args()
    result = audit(json.loads(args.results.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 1 if result["review_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
