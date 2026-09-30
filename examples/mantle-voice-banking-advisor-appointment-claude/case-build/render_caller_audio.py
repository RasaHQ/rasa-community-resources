#!/usr/bin/env python3
"""Regenerate this build's caller WAVs with Rime text-to-speech, or check them.

    python3 case-build/render_caller_audio.py --dry-run          # what is missing, and its price
    python3 case-build/render_caller_audio.py --budget-usd 4     # render the missing files (billed)
    python3 case-build/render_caller_audio.py --check            # compare local WAVs with the manifest

Only three sample WAVs are committed (`voice.caller.samples` in
`conversations.json`). Every other caller file is listed in
`caller-audio/manifest.json` with its exact text, voice and SHA-256, and is
kept out of git. `--check` says which local files still match the recorded
run; a regenerated file says the same words, but its bytes may differ.

Why Rime, and why a build-local script. The shared renderer
(`scripts/case_builds/render_caller_audio.py`) supports OpenAI, Deepgram Aura
and espeak-ng. OpenAI had no credit when this build was made, and Deepgram is
this build's speech-to-text vendor, which the harness rules out for caller
audio (no vendor transcribes its own voice). The first choice was Gemini TTS
with an accent instruction, as in the Willow Shop order-status build; it
rendered 21 of the 47 lines and then refused with HTTP 429 at its daily cap of
100 requests per model (the spend is in the ledger, and those files were not
used). Rime lists British voices in its public catalogue
(users.rime.ai/data/voices/voice_details.json), so the caller is two of them:
`carol` (Mist v2, country UK, dialect British, female) and `albion` (Coda,
country GB, dialect English, male). Rime is also the agent's text-to-speech
vendor, but not its speech-to-text vendor, so no vendor transcribes its own
voice. The agent speaks as `vashti`, a different Coda voice.

The request is Rime's HTTP endpoint (`POST https://users.rime.ai/v1/rime-tts`,
`Accept: audio/pcm`) at the fixture's sample rate, so no resampling is needed.
Each file is priced per character at the spec's per-model price. On an HTTP
429 the script stops at once and records what it rendered; it never retries.
The accent is Rime's catalogue label, not verified by a listener.
"""

from __future__ import annotations

import argparse
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
from render_caller_audio import caller_lines  # noqa: E402

RIME_URL = "https://users.rime.ai/v1/rime-tts"
MIN_SECONDS_BETWEEN_REQUESTS = 0.5


class QuotaStop(RuntimeError):
    """Rime refused for quota or rate; stop, never retry."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def voice_config(caller: dict, voice: str) -> dict:
    try:
        return caller["voices"][voice]
    except KeyError as exc:
        raise SystemExit(f"voice {voice!r} is not listed under voice.caller.voices") from exc


def file_cost(text: str, config: dict) -> float:
    return round(len(text) / 1000 * config["usd_per_1k_characters"], 8)


def render_rime(text: str, voice: str, config: dict, rate: int, env: dict) -> bytes:
    body = {"speaker": voice, "text": text, "modelId": config["model"], "samplingRate": rate,
            "lang": config.get("lang", "eng")}
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
    if caller["vendor"] != "rime":
        parser.error("this script renders Rime caller audio only")
    rate = caller["sample_rate"]
    out_dir = PROJECT / spec["voice"].get("caller_audio_dir", "case-build/caller-audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"files": {}}
    if args.check:
        return check(out_dir, manifest, caller.get("samples") or {})

    lines = caller_lines(spec)
    todo = {name: line for name, line in lines.items() if not (out_dir / name).is_file()}
    projected = round(sum(file_cost(l["text"], voice_config(caller, l["voice"])) for l in todo.values()), 6)
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
    spent, characters, rendered, stopped, last = 0.0, 0, 0, None, 0.0
    by_model: dict[str, float] = {}
    try:
        for name, line in sorted(todo.items()):
            wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            last = time.monotonic()
            config = voice_config(caller, line["voice"])
            out = out_dir / name
            try:
                pcm = render_rime(line["text"], line["voice"], config, rate, env)
            except QuotaStop as exc:
                stopped = str(exc)
                print(f"quota or rate refusal, stopping without retry: {exc}")
                break
            write_wav(pcm, rate, out)
            duration = len(pcm) / 2 / rate
            cost = file_cost(line["text"], config)
            spent += cost
            characters += len(line["text"])
            by_model[config["model"]] = round(by_model.get(config["model"], 0) + cost, 8)
            rendered += 1
            manifest["files"][name] = {
                "text": line["text"],
                "vendor": "rime",
                "model": config["model"],
                "voice": line["voice"],
                "sample_rate": rate,
                "duration_s": round(duration, 3),
                "characters": len(line["text"]),
                "sha256": sha256(out),
                "in_git": name in (caller.get("samples") or {}),
                "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cost_usd": cost,
            }
            print(f"rendered {name} ({duration:.2f} s, {line['voice']}, {config['model']})")
    finally:
        manifest.update({
            "description": caller.get("description", ""),
            "vendor": "rime",
            "voices": caller["voices"],
            "accent": caller.get("accent"),
            "regenerate": "python3 case-build/render_caller_audio.py --budget-usd 4 (from the project directory)",
            "in_git": "Only the files listed under samples are committed; the rest are regenerated, and their SHA-256s here identify the recorded run's bytes.",
            **({"samples": caller["samples"]} if caller.get("samples") else {}),
            "price": {k: caller.get(k) for k in ("price_source", "price_checked")},
        })
        for name, entry in manifest["files"].items():
            entry["in_git"] = name in (caller.get("samples") or {})
        manifest["files"] = dict(sorted(manifest["files"].items()))
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
        if rendered:
            ledger_append(PROJECT, {
                "run": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                "label": "caller audio (rime " + ", ".join(sorted(by_model)) + ")",
                "conversations": 0,
                "cost_usd": round(spent, 6),
                "by_vendor": {"rime_caller_tts": round(spent, 6)},
                "by_model": by_model,
                "files": rendered,
                "characters": characters,
                **({"stopped": stopped} if stopped else {}),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
