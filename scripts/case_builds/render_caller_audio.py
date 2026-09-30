#!/usr/bin/env python3
"""Render a voice build's scripted caller lines to WAV fixtures, once.

    python3 scripts/case_builds/render_caller_audio.py examples/<build> --budget-usd 5
    python3 scripts/case_builds/render_caller_audio.py examples/<build> --dry-run

Reads `case-build/conversations.json`, finds every caller line (`user` text,
with the spec's default caller voice or the turn's `caller_voice`), and
writes each one missing from `voice.caller_audio_dir` as 16-bit mono PCM at
`voice.caller.sample_rate`. The run then replays the same bytes every time,
so a rerun measures the agent, not a new take of the caller.

The caller voice must come from a vendor that is not the build's own
speech-to-text or text-to-speech. Supported sources:

- `openai`: OpenAI's `/v1/audio/speech` (`tts-1`, `tts-1-hd` or
  `gpt-4o-mini-tts`), asked for raw 24 kHz PCM and resampled with ffmpeg.
  The tts-1 models bill per character (`usd_per_1m_characters`).
  `gpt-4o-mini-tts` bills per token and takes free-text `instructions` (an
  accent, for example). Priced per token (`usd_per_1m_input_tokens`,
  `usd_per_1m_audio_output_tokens`), it is requested as a server-sent event
  stream, whose closing `speech.audio.done` event carries the usage, so each
  file's cost comes from the tokens OpenAI reported for it. The budget check
  before rendering has no usage yet, so it projects the output tokens from
  the characters (`estimate_audio_tokens_per_character`, default 4).
- `deepgram`: Deepgram Aura (`/v1/speak`, `model` is the voice, for example
  `aura-2-athena-en`), asked for raw 16-bit PCM at `voice.caller.sample_rate`
  directly, so nothing is resampled. Billed per character
  (`usd_per_1m_characters`); the characters are the ones Deepgram reports in
  its `dg-char-count` response header, or the text length if it sends none.
- `espeak-ng`: the local formant synthesiser, free and robotic.

Every file is listed in `manifest.json` next to it with the exact text, the
vendor, model and voice, its SHA-256 and duration (and, for token pricing,
the tokens and cost). A spec `accent` block (what was requested, and its
status) is copied into the manifest: an accent asked for through
instructions is only what was requested until a person has listened. The
spend is added to the build's spend ledger. Keys load into this process only
and are never printed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import REPO_ROOT, agent_env, ledger_append, ledger_total, load_spec  # noqa: E402
from voice_driver import turn_audio_name  # noqa: E402

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_PCM_RATE = 24000
DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
BILLED_VENDORS = ("openai", "deepgram")


def caller_lines(spec: dict) -> dict[str, dict]:
    caller = spec["voice"]["caller"]
    lines: dict[str, dict] = {}
    for conv in spec["conversations"]:
        for turn in conv["turns"]:
            voice = turn.get("caller_voice") or caller["voice"]
            name = turn_audio_name(turn, caller["voice"])
            lines.setdefault(name, {"text": turn["user"], "voice": voice, "used_by": []})
            lines[name]["used_by"].append(conv["id"])
    return lines


def resample_to_wav(pcm: bytes, source_rate: int, target_rate: int, out: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is needed to resample the caller audio")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(source_rate),
         "-ac", "1", "-i", "pipe:0", "-ar", str(target_rate), "-ac", "1", "-sample_fmt", "s16",
         "-bitexact", str(out)],
        input=pcm, check=True,
    )


def token_priced(caller: dict) -> bool:
    return caller.get("usd_per_1m_audio_output_tokens") is not None


def token_cost(usage: dict, caller: dict) -> float:
    """USD for one render from OpenAI's reported usage and the spec's per-token prices."""
    return round(
        (usage.get("input_tokens") or 0) * caller["usd_per_1m_input_tokens"] / 1e6
        + (usage.get("output_tokens") or 0) * caller["usd_per_1m_audio_output_tokens"] / 1e6,
        8,
    )


def estimate_cost(lines: list[dict], caller: dict) -> float | None:
    """Pre-render projection, used only for the budget check."""
    chars = sum(len(line["text"]) for line in lines)
    if token_priced(caller):
        # Input: text plus the instructions, at a generous 1 token per 3 characters.
        instr = len(caller.get("instructions") or "")
        input_tokens = sum((len(line["text"]) + instr) / 3 for line in lines)
        output_tokens = chars * float(caller.get("estimate_audio_tokens_per_character", 4.0))
        return round(input_tokens * caller["usd_per_1m_input_tokens"] / 1e6
                     + output_tokens * caller["usd_per_1m_audio_output_tokens"] / 1e6, 6)
    per_char = caller.get("usd_per_1m_characters")
    return round(chars * per_char / 1e6, 6) if per_char is not None else None


def parse_speech_sse(lines: Any) -> tuple[bytes, dict]:
    """PCM and usage from `/v1/audio/speech` with `stream_format: sse`."""
    pcm = bytearray()
    usage: dict = {}
    for raw in lines:
        line = (raw.decode() if isinstance(raw, bytes) else raw).strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            continue
        event = json.loads(payload)
        if event.get("type") == "speech.audio.delta":
            pcm += base64.b64decode(event["audio"])
        elif event.get("type") == "speech.audio.done":
            usage = event.get("usage") or {}
    return bytes(pcm), usage


def render_openai(text: str, voice: str, caller: dict, env: dict) -> tuple[bytes, dict]:
    body = {"model": caller["model"], "voice": voice, "input": text, "response_format": "pcm"}
    if caller.get("instructions"):
        body["instructions"] = caller["instructions"]
    if token_priced(caller):
        body["stream_format"] = "sse"
    request = urllib.request.Request(
        OPENAI_SPEECH_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        if token_priced(caller):
            pcm, usage = parse_speech_sse(response)
            if not usage:
                raise RuntimeError("the speech stream ended without a usage block; cannot price this render")
            return pcm, usage
        return response.read(), {}


def render_deepgram(text: str, voice: str, rate: int, out: Path, env: dict) -> int:
    """Write Deepgram Aura speech as a WAV at *rate*; return the characters billed."""
    query = urllib.parse.urlencode({"model": voice, "encoding": "linear16", "sample_rate": rate, "container": "none"})
    request = urllib.request.Request(
        f"{DEEPGRAM_SPEAK_URL}?{query}", data=json.dumps({"text": text}).encode(), method="POST",
        headers={"Authorization": f"Token {env['DEEPGRAM_API_KEY']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        pcm = response.read()
        billed = response.headers.get("dg-char-count")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return int(billed) if billed and billed.isdigit() else len(text)


def render_espeak(text: str, voice: str, out: Path, target_rate: int) -> None:
    raw = out.with_suffix(".espeak.wav")
    subprocess.run(["espeak-ng", "-v", voice, "-w", str(raw), text], check=True)
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-ar",
                    str(target_rate), "-ac", "1", "-sample_fmt", "s16", "-bitexact", str(out)], check=True)
    raw.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--budget-usd", type=float, help="cap on the build's ledger total, renders included")
    parser.add_argument("--dry-run", action="store_true", help="list what would be rendered and its price")
    args = parser.parse_args()
    project = Path(args.project)
    if not project.is_absolute():
        project = REPO_ROOT / project
    spec = load_spec(project)
    voice = spec["voice"]
    caller = voice["caller"]
    out_dir = project / voice.get("caller_audio_dir", "case-build/caller-audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"files": {}}

    lines = caller_lines(spec)
    todo = {name: line for name, line in lines.items() if not (out_dir / name).is_file()}
    chars = sum(len(line["text"]) for line in todo.values())
    per_char = caller.get("usd_per_1m_characters")
    estimate = estimate_cost(list(todo.values()), caller)
    print(f"{len(lines)} caller lines, {len(todo)} to render, {chars} characters, estimated {estimate} USD"
          + (" (projected from characters; billed from reported tokens)" if token_priced(caller) else ""))
    if args.dry_run or not todo:
        return 0
    if caller["vendor"] in BILLED_VENDORS:
        if estimate is None:
            print("no price in the spec; refusing to spend without one")
            return 2
        if args.budget_usd is None:
            parser.error("--budget-usd is required to render billed audio")
        if ledger_total(project) + estimate > args.budget_usd:
            print(f"rendering would cross the {args.budget_usd} USD cap; nothing rendered")
            return 2
    env = agent_env(project)
    rendered_chars = 0
    rendered_cost = 0.0
    tokens = {"input_tokens": 0, "output_tokens": 0}
    try:
        for name, line in sorted(todo.items()):
            out = out_dir / name
            usage: dict = {}
            if caller["vendor"] == "openai":
                pcm, usage = render_openai(line["text"], line["voice"], caller, env)
                rendered_chars += len(line["text"])
                if usage:
                    rendered_cost += token_cost(usage, caller)
                    for key in tokens:
                        tokens[key] += usage.get(key) or 0
                elif per_char is not None:
                    rendered_cost += len(line["text"]) * per_char / 1e6
                resample_to_wav(pcm, OPENAI_PCM_RATE, caller["sample_rate"], out)
            elif caller["vendor"] == "deepgram":
                billed_chars = render_deepgram(line["text"], line["voice"], caller["sample_rate"], out, env)
                rendered_chars += billed_chars
                rendered_cost += billed_chars * per_char / 1e6
                usage = {"characters_billed": billed_chars}
            elif caller["vendor"] == "espeak-ng":
                render_espeak(line["text"], line["voice"], out, caller["sample_rate"])
            else:
                raise ValueError(f"unknown caller vendor {caller['vendor']!r}")
            with wave.open(str(out), "rb") as w:
                duration = w.getnframes() / w.getframerate()
            manifest["files"][name] = {
                "text": line["text"],
                "vendor": caller["vendor"],
                "model": caller.get("model"),
                "voice": line["voice"],
                "sample_rate": caller["sample_rate"],
                "duration_s": round(duration, 3),
                "characters": len(line["text"]),
                "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **({"usage": {k: usage.get(k) for k in ("input_tokens", "output_tokens")},
                    "cost_usd": token_cost(usage, caller)} if usage and token_priced(caller) else {}),
                **({"characters_billed": usage["characters_billed"],
                    "cost_usd": round(usage["characters_billed"] * per_char / 1e6, 8)}
                   if usage.get("characters_billed") is not None else {}),
            }
            print(f"rendered {name} ({duration:.2f} s)")
    finally:
        manifest.update({
            "description": caller.get("description", ""),
            "vendor": caller["vendor"],
            "model": caller.get("model"),
            **({"instructions": caller["instructions"]} if caller.get("instructions") else {}),
            **({"accent": caller["accent"]} if caller.get("accent") else {}),
            **({"samples": caller["samples"]} if caller.get("samples") else {}),
            "price": {k: caller.get(k) for k in (
                "usd_per_1m_characters", "usd_per_1m_input_tokens", "usd_per_1m_audio_output_tokens",
                "price_source", "price_checked") if caller.get(k) is not None},
        })
        manifest["files"] = dict(sorted(manifest["files"].items()))
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
        if rendered_chars and rendered_cost:
            cost = round(rendered_cost, 6)
            ledger_append(project, {
                "run": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                "label": f"caller audio ({caller['vendor']} {caller.get('model')})",
                "conversations": 0,
                "cost_usd": cost,
                "by_vendor": {f"{caller['vendor']}_tts": cost},
                "characters": rendered_chars,
                **({"tokens": tokens} if token_priced(caller) else {}),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
