"""Inspect saved Northgate voice results, without making provider calls.

This recognises this example's English confirmation question only. Audio in
a turn is not proof that the complete question played or that a human heard it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


QUESTION = "Would you like to confirm this transaction?"
MISSING_REASON = "tts_produced_no_audio_without_barge_in"


def audit(report: dict) -> dict:
    rows = []
    for conversation in report["conversations"]:
        events = conversation.get("log_event_details", {}).get(
            "voice_channel.audio_missing", []
        )
        for index, turn in enumerate(conversation["turns"], 1):
            questions = [text for text in turn.get("bot", []) if QUESTION in text]
            if not questions:
                continue
            observation = turn.get("extra", {})
            matches = [
                event for event in events
                if event.get("text") in questions
                and bool(conversation.get("conversation_id"))
                and event.get("conversation_id") == conversation.get("conversation_id")
                and event.get("reason") == MISSING_REASON
            ]
            # These event summaries have no turn index. Repeated identical
            # questions cannot be assigned to one turn from text alone.
            unique_question = all(
                sum(text in item.get("bot", []) for item in conversation["turns"]) == 1
                for text in questions
            )
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
            if matches and no_audio and unique_question:
                finding = "missing_audio_corroborated"
            elif matches:
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
        "review_required": not rows or any(
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
