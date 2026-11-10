#!/usr/bin/env python3
"""Did the caller hear what the tracker says the agent said? Transcribe the agent's audio and compare.

    <build>/.venv/bin/python scripts/case_builds/tts_intelligibility.py examples/<build> <label> \\
        --raw <build>/case-build/results/raw/<run tag> --model <faster-whisper model or folder>

For a voice run made with `voice.save_bot_audio: true`, each file
`bot-audio/<conversation>-<turn>.wav` holds everything the driver's speaker
received after caller turn <turn> (0 is the greeting). This script
transcribes each file with faster-whisper (a judge model, ideally larger than
and separate from the build's own speech-to-text) and compares the
transcript with the text of the tracker's bot events for that turn, using the
harness's word error rate (numbers compared digit by digit).

Turns are aligned by user event, so a caller turn that speech-to-text split
in two shifts the per-turn pairing; the per-conversation figures (all of a
call's bot text against all of its audio) do not depend on that. References
the agent spells out ("R Q, nine three six six") are checked on their own:
did the judge hear the digits?

It also measures each file's voiced span (the part above -40 dBFS), so a
text-to-speech engine that pads with silence or keeps talking past the text
shows up as audio seconds per character.

Writes `<build>/case-build/results/<label>/tts-intelligibility.json`. Local
only: no network, no spend. Needs faster-whisper, so run it with a build's
own venv.
"""

from __future__ import annotations

import argparse
import audioop
import json
import re
import statistics
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import voice_driver as vd  # noqa: E402
from harness import REPO_ROOT  # noqa: E402


_DIGIT = r"(?:zero|one|two|three|four|five|six|seven|eight|nine)"
_REFERENCE_RE = re.compile(rf"\b([A-Z]) ([A-Z]),? ({_DIGIT}(?: {_DIGIT}){{3}})\b")
_WORD_DIGITS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine".split())}


def spoken_references(text: str) -> list[str]:
    """'R Q, nine three six six' -> ['RQ-9366'] for each reference in the text."""
    return [f"{a}{b}-" + "".join(_WORD_DIGITS[w] for w in digits.split())
            for a, b, digits in _REFERENCE_RE.findall(text)]


def bot_texts_by_turn(tracker: dict) -> list[list[str]]:
    """Bot texts after each user event: [greeting, after turn 1, ...], /session_end excluded."""
    turns: list[list[str]] = []
    for event in tracker.get("events", []):
        if event.get("event") == "user":
            if event.get("text") == "/session_end":
                break
            turns.append([])
        elif event.get("event") == "bot" and turns and event.get("text"):
            turns[-1].append(event["text"])
    return turns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("label")
    parser.add_argument("--raw", required=True, type=Path, help="the run's raw folder, holding bot-audio/")
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    project = Path(args.project)
    if not project.is_absolute():
        project = REPO_ROOT / project
    results_dir = project / "case-build" / "results" / args.label
    audio_dir = args.raw / "bot-audio"

    import numpy as np
    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads)
    rows = []
    all_said: dict[str, str] = {}
    for tracker_path in sorted((results_dir / "trackers").glob("*.json")):
        conversation = tracker_path.stem
        texts = bot_texts_by_turn(json.loads(tracker_path.read_text()))
        all_said[conversation] = " ".join(" ".join(t) for t in texts)
        for wav in sorted(audio_dir.glob(f"*-{conversation}-*.wav")):
            turn = int(wav.stem.rsplit("-", 1)[1])
            if turn >= len(texts):
                continue
            with wave.open(str(wav)) as w:
                pcm, rate = w.readframes(w.getnframes()), w.getframerate()
            on, off = vd.voiced_bounds(pcm, rate)
            pcm16, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
            audio = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
            started = time.monotonic()
            segments, _ = model.transcribe(audio, beam_size=5, language="en", vad_filter=True)
            heard = " ".join(s.text.strip() for s in segments).strip()
            said = " ".join(texts[turn])
            rows.append({
                "conversation": conversation, "turn": turn, "said": said, "heard": heard,
                "wer": vd.word_error_rate(said, heard),
                "audio_s": round(len(pcm) / 2 / rate, 2),
                "voiced_s": round((off - on) / rate, 2),
                "characters": len(said),
                "judge_s": round(time.monotonic() - started, 2),
            })
            print(f"{conversation} {turn} wer={rows[-1]['wer']} {heard[:80]!r}", flush=True)
    conversations = []
    for conversation in sorted({r["conversation"] for r in rows}):
        mine = sorted((r for r in rows if r["conversation"] == conversation), key=lambda r: r["turn"])
        said = all_said[conversation]
        heard = " ".join(r["heard"] for r in mine)
        refs = spoken_references(said)
        conversations.append({
            "conversation": conversation,
            "wer": vd.word_error_rate(said, heard),
            "references": [{"reference": ref, "digits_heard": vd.check_tokens(heard, [
                {"token": ref.split("-")[1], "kind": "reference"}])[0]["normalised"]} for ref in refs],
        })
    references = [ref for c in conversations for ref in c["references"]]
    wers = [r["wer"] for r in rows if r["wer"] is not None]
    chars = sum(r["characters"] for r in rows)
    report = {
        "judge": {"engine": "faster-whisper", "model": args.model, "beam_size": 5, "vad_filter": True},
        "files": len(rows),
        "wer_mean": round(statistics.mean(wers), 4) if wers else None,
        "wer_median": round(statistics.median(wers), 4) if wers else None,
        "turns_wer_zero": sum(1 for w in wers if w == 0),
        "turns_wer_over_0_2": sum(1 for w in wers if w > 0.2),
        "conversation_wer_mean": round(statistics.mean(c["wer"] for c in conversations if c["wer"] is not None), 4)
        if conversations else None,
        "references_spoken": len(references),
        "references_digits_heard": sum(1 for r in references if r["digits_heard"]),
        "conversations": conversations,
        "voiced_seconds_per_100_characters": round(100 * sum(r["voiced_s"] for r in rows) / chars, 2) if chars else None,
        "rows": rows,
    }
    (results_dir / "tts-intelligibility.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "conversations")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
