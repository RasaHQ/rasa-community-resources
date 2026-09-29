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
  Billed per character for tts-1 models; the price comes from the spec.
- `espeak-ng`: the local formant synthesiser, free and robotic.

Every file is listed in `manifest.json` next to it with the exact text, the
vendor, model and voice, its SHA-256 and duration. The spend is added to the
build's spend ledger. Keys load into this process only and are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import REPO_ROOT, agent_env, ledger_append, ledger_total, load_spec  # noqa: E402
from voice_driver import turn_audio_name  # noqa: E402

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_PCM_RATE = 24000


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


def render_openai(text: str, voice: str, caller: dict, env: dict) -> bytes:
    body = {"model": caller["model"], "voice": voice, "input": text, "response_format": "pcm"}
    if caller.get("instructions"):
        body["instructions"] = caller["instructions"]
    request = urllib.request.Request(
        OPENAI_SPEECH_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


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
    estimate = round(chars * per_char / 1e6, 6) if per_char is not None else None
    print(f"{len(lines)} caller lines, {len(todo)} to render, {chars} characters, estimated {estimate} USD")
    if args.dry_run or not todo:
        return 0
    if caller["vendor"] == "openai":
        if estimate is None:
            print("no per-character price in the spec; refusing to spend without one")
            return 2
        if args.budget_usd is None:
            parser.error("--budget-usd is required to render billed audio")
        if ledger_total(project) + estimate > args.budget_usd:
            print(f"rendering would cross the {args.budget_usd} USD cap; nothing rendered")
            return 2
    env = agent_env(project)
    rendered_chars = 0
    try:
        for name, line in sorted(todo.items()):
            out = out_dir / name
            if caller["vendor"] == "openai":
                pcm = render_openai(line["text"], line["voice"], caller, env)
                rendered_chars += len(line["text"])
                resample_to_wav(pcm, OPENAI_PCM_RATE, caller["sample_rate"], out)
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
            }
            print(f"rendered {name} ({duration:.2f} s)")
    finally:
        manifest.update({
            "description": caller.get("description", ""),
            "vendor": caller["vendor"],
            "model": caller.get("model"),
            "price": {k: caller.get(k) for k in ("usd_per_1m_characters", "price_source", "price_checked")},
        })
        manifest["files"] = dict(sorted(manifest["files"].items()))
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
        if rendered_chars and per_char is not None:
            cost = round(rendered_chars * per_char / 1e6, 6)
            ledger_append(project, {
                "run": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                "label": f"caller audio ({caller['vendor']} {caller.get('model')})",
                "conversations": 0,
                "cost_usd": cost,
                "by_vendor": {f"{caller['vendor']}_tts": cost},
                "characters": rendered_chars,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
