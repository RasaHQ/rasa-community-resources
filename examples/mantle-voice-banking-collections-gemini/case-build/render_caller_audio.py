#!/usr/bin/env python3
"""Regenerate this build's caller WAVs with Gemini or Rime text-to-speech, or check them.

    python3 case-build/render_caller_audio.py --dry-run          # what is missing, and its price
    python3 case-build/render_caller_audio.py --budget-usd 4     # render the missing files (billed)
    python3 case-build/render_caller_audio.py --check            # compare local WAVs with the manifest

Only three sample WAVs are committed (`voice.caller.samples` in
`conversations.json`). Every other caller file is listed in
`caller-audio/manifest.json` with its exact text, voice and SHA-256, and is
kept out of git. Rendering is not deterministic: a regenerated file says the
same words but its bytes, and so its SHA-256, differ from the recorded run's.
`--check` says which local files still match the recorded run.

Why a build-local script: the shared renderer
(`scripts/case_builds/render_caller_audio.py`) supports OpenAI, Deepgram Aura
and espeak-ng. This build makes no OpenAI calls, and Deepgram is this build's
own speech-to-text vendor, which the harness rules out for caller audio (no
vendor transcribes its own voice). The script is the Willow Shop
order-status build's, with one addition: each voice's director's notes
(`voice.caller.director_notes` in `conversations.json`) go before the line,
asking for US Spanish. Gemini does not speak the notes; a local Whisper check
of every file found only the script line. The file name still hashes the
voice and the line alone, so the harness replays the output unchanged.

Voices listed under `voice.caller.rime_voices` are rendered by Rime's HTTP
endpoint instead (`POST https://users.rime.ai/v1/rime-tts`, `Accept:
audio/pcm`, at the fixture rate), priced per character, as in the Northgate
advisor build. Gemini's rate limit stopped the first render after 23 lines
(`voice.caller.gemini_rate_limit`), so half the calls use a Rime US Spanish
speaker. A 429 from either vendor stops the script; it never retries.

The request is Gemini's `generateContent` with `responseModalities: AUDIO`
and a prebuilt voice; the reply is 24 kHz 16-bit PCM, resampled here to the
fixture rate with ffmpeg. Each file is priced from the `usageMetadata` Gemini
returns for it (text tokens in, audio tokens out) at the spec's per-token
prices. On any HTTP 429 or quota error the script stops at once and records
what it rendered; it never retries.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
REPO = PROJECT.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "case_builds"))

from harness import agent_env, ledger_append, ledger_total, load_spec  # noqa: E402
from render_caller_audio import caller_lines, resample_to_wav  # noqa: E402

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RIME_URL = "https://users.rime.ai/v1/rime-tts"
GEMINI_PCM_RATE = 24000
# Pace requests under the 10-a-minute limit (a first run at 6 s got HTTP 429
# on the 15th request); a 429 still stops the run.
MIN_SECONDS_BETWEEN_REQUESTS = 7.5


class QuotaStop(RuntimeError):
    """Gemini refused for quota or rate; stop, never retry."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cost(usage: dict, caller: dict) -> float:
    return round(
        (usage.get("promptTokenCount") or 0) * caller["usd_per_1m_input_tokens"] / 1e6
        + (usage.get("candidatesTokenCount") or 0) * caller["usd_per_1m_audio_output_tokens"] / 1e6,
        8,
    )


def estimate(lines: list[dict], caller: dict) -> float:
    """Projection for the budget check only. Gemini: ~1 token per 4 characters in, 25 audio tokens a
    second out at ~14 characters a second of speech. Rime: its per-character price."""
    rime = caller.get("rime_voices") or {}
    total = 0.0
    for line in lines:
        chars = len(line["text"])
        if line["voice"] in rime:
            total += chars / 1000 * rime[line["voice"]]["usd_per_1k_characters"]
        else:
            total += (chars / 4 * caller["usd_per_1m_input_tokens"] / 1e6
                      + chars / 14 * 25 * caller["usd_per_1m_audio_output_tokens"] / 1e6)
    return round(total, 6)


def render_gemini(text: str, voice: str, caller: dict, env: dict) -> tuple[bytes, dict]:
    notes = (caller.get("director_notes") or {}).get(voice, "")
    body = {
        "contents": [{"parts": [{"text": notes + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    request = urllib.request.Request(
        GEMINI_URL.format(model=caller["model"]), data=json.dumps(body).encode(), method="POST",
        headers={"x-goog-api-key": env["GEMINI_API_KEY"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:600]
        if exc.code == 429 or "RESOURCE_EXHAUSTED" in detail or "PerDay" in detail:
            raise QuotaStop(f"HTTP {exc.code}: {detail}") from exc
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    parts = data["candidates"][0]["content"]["parts"]
    pcm = b"".join(base64.b64decode(p["inlineData"]["data"]) for p in parts if "inlineData" in p)
    if not pcm:
        raise RuntimeError(f"no audio in the reply: {json.dumps(data)[:300]}")
    return pcm, data.get("usageMetadata") or {}


def render_rime(text: str, voice: str, config: dict, rate: int, env: dict) -> bytes:
    body = {"speaker": voice, "text": text, "modelId": config["model"], "samplingRate": rate,
            "lang": config.get("lang", "spa")}
    request = urllib.request.Request(
        RIME_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {env['RIME_API_KEY']}", "Content-Type": "application/json",
                 "Accept": "audio/pcm"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            pcm = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:600]
        if exc.code == 429:
            raise QuotaStop(f"HTTP {exc.code}: {detail}") from exc
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if not pcm:
        raise RuntimeError("no audio in the reply")
    return pcm


def write_wav(pcm: bytes, rate: int, out: Path) -> None:
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def check(out_dir: Path, manifest: dict, samples: dict) -> int:
    missing, changed, ok = [], [], 0
    for name, entry in sorted(manifest.get("files", {}).items()):
        path = out_dir / name
        if not path.is_file():
            missing.append(name)
        elif sha256(path) != entry["sha256"]:
            changed.append(name)
        else:
            ok += 1
    print(f"{ok} match the recorded run, {len(changed)} differ, {len(missing)} missing "
          f"(committed samples: {', '.join(sorted(samples)) or 'none'})")
    for name in changed:
        print(f"  differs: {name}")
    for name in missing:
        print(f"  missing: {name}  ({manifest['files'][name]['text']!r})")
    return 0 if not changed and not missing else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget-usd", type=float, help="cap on the build's ledger total, renders included")
    parser.add_argument("--dry-run", action="store_true", help="list what would be rendered and its price")
    parser.add_argument("--check", action="store_true", help="compare local WAVs with the manifest")
    args = parser.parse_args()
    spec = load_spec(PROJECT)
    caller = spec["voice"]["caller"]
    if caller["vendor"] != "gemini":
        parser.error("this script renders Gemini caller audio, and Rime for voices under rime_voices")
    out_dir = PROJECT / spec["voice"].get("caller_audio_dir", "case-build/caller-audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"files": {}}
    if args.check:
        return check(out_dir, manifest, caller.get("samples") or {})

    lines = caller_lines(spec)
    todo = {name: line for name, line in lines.items() if not (out_dir / name).is_file()}
    projected = estimate(list(todo.values()), caller)
    print(f"{len(lines)} caller lines, {len(todo)} to render, "
          f"{sum(len(l['text']) for l in todo.values())} characters, projected {projected} USD")
    if args.dry_run or not todo:
        return 0
    if args.budget_usd is None:
        parser.error("--budget-usd is required to render billed audio")
    if ledger_total(PROJECT) + projected > args.budget_usd:
        print(f"rendering would cross the {args.budget_usd} USD cap; nothing rendered")
        return 2

    env = agent_env(PROJECT)
    rime = caller.get("rime_voices") or {}
    spent, tokens, rendered, stopped = 0.0, {"input_tokens": 0, "output_tokens": 0}, 0, None
    by_vendor = {"gemini_tts": 0.0, "rime_caller_tts": 0.0}
    last = 0.0
    try:
        for name, line in sorted(todo.items()):
            out = out_dir / name
            if line["voice"] in rime:
                config = rime[line["voice"]]
                try:
                    pcm = render_rime(line["text"], line["voice"], config, caller["sample_rate"], env)
                except QuotaStop as exc:
                    stopped = str(exc)
                    print(f"quota or rate refusal, stopping without retry: {exc}")
                    break
                write_wav(pcm, caller["sample_rate"], out)
                file_cost = round(len(line["text"]) / 1000 * config["usd_per_1k_characters"], 8)
                by_vendor["rime_caller_tts"] += file_cost
                entry = {"vendor": "rime", "model": config["model"], "lang": config.get("lang"),
                         "usage": {"characters": len(line["text"])}}
            else:
                wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - last)
                if wait > 0:
                    time.sleep(wait)
                last = time.monotonic()
                try:
                    pcm, usage = render_gemini(line["text"], line["voice"], caller, env)
                except QuotaStop as exc:
                    stopped = str(exc)
                    print(f"quota or rate refusal, stopping without retry: {exc}")
                    break
                resample_to_wav(pcm, GEMINI_PCM_RATE, caller["sample_rate"], out)
                file_cost = cost(usage, caller)
                by_vendor["gemini_tts"] += file_cost
                tokens["input_tokens"] += usage.get("promptTokenCount") or 0
                tokens["output_tokens"] += usage.get("candidatesTokenCount") or 0
                entry = {"vendor": "gemini", "model": caller["model"],
                         "director_notes": bool((caller.get("director_notes") or {}).get(line["voice"])),
                         "usage": {"input_tokens": usage.get("promptTokenCount"),
                                   "output_tokens": usage.get("candidatesTokenCount")}}
            with wave.open(str(out), "rb") as w:
                duration = w.getnframes() / w.getframerate()
            spent += file_cost
            rendered += 1
            manifest["files"][name] = {
                "text": line["text"],
                **{k: v for k, v in entry.items() if k != "usage"},
                "voice": line["voice"],
                "sample_rate": caller["sample_rate"],
                "duration_s": round(duration, 3),
                "characters": len(line["text"]),
                "sha256": sha256(out),
                "in_git": name in (caller.get("samples") or {}),
                "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "usage": entry["usage"],
                "cost_usd": file_cost,
            }
            print(f"rendered {name} ({entry['vendor']}, {duration:.2f} s)")
    finally:
        manifest.update({
            "description": caller.get("description", ""),
            "vendor": "gemini" if not rime else "gemini and rime",
            "model": caller["model"],
            **({"rime_voices": rime} if rime else {}),
            **({"gemini_rate_limit": caller["gemini_rate_limit"]} if caller.get("gemini_rate_limit") else {}),
            "regenerate": "python3 case-build/render_caller_audio.py --budget-usd 4 (from the project directory)",
            "in_git": "Only the files listed under samples are committed; the rest are regenerated, and their SHA-256s here identify the recorded run's bytes.",
            **({"samples": caller["samples"]} if caller.get("samples") else {}),
            **({"director_notes": caller["director_notes"]} if caller.get("director_notes") else {}),
            **({"accent": caller["accent"]} if caller.get("accent") else {}),
            "price": {k: caller.get(k) for k in (
                "usd_per_1m_input_tokens", "usd_per_1m_audio_output_tokens", "price_source", "price_checked")},
        })
        for name, entry in manifest["files"].items():
            entry["in_git"] = name in (caller.get("samples") or {})
        manifest["files"] = dict(sorted(manifest["files"].items()))
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
        if rendered:
            ledger_append(PROJECT, {
                "run": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                "label": "caller audio (" + " and ".join(
                    v for v, used in (("gemini " + caller["model"], by_vendor["gemini_tts"]),
                                      ("rime", by_vendor["rime_caller_tts"])) if used) + ")",
                "conversations": 0,
                "cost_usd": round(spent, 6),
                "by_vendor": {k: round(v, 6) for k, v in by_vendor.items() if v},
                "files": rendered,
                "tokens": tokens,
                **({"stopped": stopped} if stopped else {}),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
