#!/usr/bin/env python3
"""Replay the fixture corpus through every reachable ASR adapter and compare.

    make bench                 local adapters only — no credentials, no spend
    make bench BENCH_ARGS=--include-cloud
                               also the configured cloud vendors (costs money)

The question this answers is the one every voice team actually has: *on this
audio, do these vendors agree, and how fast are they?* Rasa's ASR events carry
no confidence — `NewTranscript` has one field, `text` — so agreement between
independent vendors is the only quality signal available without forking the
engine. See `voicerouter/bench.py` for the arithmetic and the reasoning.

Two invariants this script exists to hold:

1. **The default run never costs anything.** It never requires credentials,
   never contacts a paid vendor, and never fails because one is unconfigured.
   An adapter that cannot run here is *skipped and reported as skipped*.
2. **No fabricated ground truth.** WER appears only for fixtures carrying a
   reference transcript. With none, the column is absent — not zero, not blank.

Reachability is not decided here. It is `scripts/probe_providers.py:probe()`,
the same function behind `make probe`, so the benchmark and the diagnostic can
never disagree about which vendors this machine can reach.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CORPUS = ROOT / "tests" / "fixtures" / "audio"

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    ("\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m")
    if sys.stdout.isatty() else ("", "", "", "", "", "")
)

#: Adapters that run entirely on this machine. Only these are measured by
#: default. The list is by dotted path rather than label because a label is
#: operator-chosen text and must not be what decides whether money is spent.
LOCAL_ASR_PATHS = frozenset({
    "voicerouter.providers.vosk.VoskASR",
    "voicerouter.providers.whisper.FasterWhisperASR",
})

#: A fifth of a second of digital silence, as a 16 kHz mono PCM16 WAV. Used
#: only to force a model load before the clock starts; it carries no speech, so
#: no adapter can score anything on it.
SILENCE_WAV = (
    b"RIFF" + (36 + 6400).to_bytes(4, "little") + b"WAVEfmt "
    + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
    + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
    + (16).to_bytes(2, "little")
    + b"data" + (6400).to_bytes(4, "little") + b"\x00" * 6400
)


def discover_vosk_model() -> str:
    """Find an unpacked Vosk model under `models/`, if one was downloaded.

    Vosk is the second credential-free adapter, and a benchmark with one
    adapter cannot compute agreement at all — so the difference between "a
    model is present" and "the config names its path" decides whether this tool
    produces its headline output. The models are far too large to commit
    (~68 MB) and `models/` is already git-ignored, so discovery here saves an
    edit to `integrations.yml` that would otherwise be mandatory and easy to
    forget. Nothing is downloaded; if no model is present, Vosk simply skips.
    """
    models = ROOT / "models"
    if not models.is_dir():
        return ""
    for candidate in sorted(models.glob("vosk-model*")):
        if (candidate / "am").is_dir() or (candidate / "graph").is_dir():
            return str(candidate)
    return ""


def load_corpus() -> list:
    """Read the committed fixtures and their reference transcripts."""
    from voicerouter.bench import Fixture

    manifest_path = CORPUS / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = []
    for entry in manifest.get("utterances", []):
        audio = CORPUS / entry["audio"]
        if audio.is_file():
            fixtures.append(
                Fixture(entry["name"], str(audio), entry.get("reference") or None)
            )
    return fixtures


async def transcribe_once(engine, wav_bytes: bytes) -> str:
    """Push one complete utterance through an ASR engine and collect the text.

    This drives the same surface the voice channel drives — connect, send
    chunks, signal done, read events — rather than reaching past it to a
    vendor SDK. A benchmark that bypassed the engine would measure something
    the router will never actually run.
    """
    from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript
    from voicerouter.audio import to_rasa_audio

    # `to_rasa_audio` owns WAV parsing and resampling for the whole package;
    # the declared header rate wins over any assumption made here.
    audio = to_rasa_audio(wav_bytes, 16000, engine.audio_format, is_wav=True)

    await engine.connect()
    try:
        # 20 ms of audio per chunk, which is what a real channel delivers.
        # One giant chunk would defeat endpointing and flatter batch models.
        step = int(engine.audio_format.bytes_per_second * 0.02) or 1
        for offset in range(0, len(audio.data), step):
            await engine.send_audio_chunks(audio[offset : offset + step])
        await engine.signal_audio_done()

        parts: list[str] = []
        async for event in engine.stream_asr_events():
            if isinstance(event, NewTranscript):
                parts.append(event.text)
        return " ".join(p for p in parts if p).strip()
    finally:
        await engine.close_connection()


async def run_bench(include_cloud: bool):
    """Measure every reachable adapter over the corpus."""
    from probe_providers import probe
    from voicerouter.bench import BenchReport, Observation

    report = BenchReport(fixtures=load_corpus())
    if not report.fixtures:
        print(f"{RED}No fixtures found in {CORPUS.relative_to(ROOT)}.{RESET}")
        print(f"{DIM}Generate them with: python3 scripts/make_fixtures.py{RESET}")
        return report

    print(f"\n{BOLD}ASR bench{RESET}  {DIM}{len(report.fixtures)} fixtures, "
          f"{'local + cloud' if include_cloud else 'local adapters only'}{RESET}\n")

    overrides: dict[str, dict] = {}
    if model_path := discover_vosk_model():
        overrides["voicerouter.providers.vosk.VoskASR"] = {"model_path": model_path}
        print(f"  {DIM}vosk model: {Path(model_path).name}{RESET}")

    for result in probe("asr", overrides=overrides):
        if not result.reachable:
            report.skipped[result.label] = result.reason
            marker = f"{YELLOW}skip{RESET}" if result.skipped else f"{RED}error{RESET}"
            print(f"  {marker}  {result.label:<16} {result.reason[:78]}")
            continue
        if not include_cloud and result.name not in LOCAL_ASR_PATHS:
            # Reachable, but reaching it would place a billable call. Refusing
            # by default is the invariant, so this is a skip with its own
            # reason rather than a silent omission.
            report.skipped[result.label] = "cloud vendor — not run by default"
            print(f"  {YELLOW}skip{RESET}  {result.label:<16} "
                  f"cloud vendor; add --include-cloud to spend real money on it")
            continue

        print(f"  {GREEN}run{RESET}   {result.label:<16} ", end="", flush=True)

        # Warm the engine before timing. A local model loads several seconds of
        # weights on its first connect, and charging that to fixture #1 would
        # report a latency distribution whose maximum is really a one-off
        # startup cost — and would flatter cloud vendors, which have no such
        # cost, for a reason unrelated to how fast they transcribe.
        try:
            await transcribe_once(result.engine, SILENCE_WAV)
        except Exception:  # noqa: BLE001 - warm-up failure is not a result
            pass

        for fixture in report.fixtures:
            wav = Path(fixture.path).read_bytes()
            started = time.monotonic()
            try:
                text = await transcribe_once(result.engine, wav)
                error = ""
            except Exception as exc:  # noqa: BLE001 - a vendor failure is a result
                text, error = "", f"{type(exc).__name__}: {exc}"
            report.observations.append(
                Observation(
                    fixture.name, result.label, text,
                    (time.monotonic() - started) * 1000.0, error,
                )
            )
            print("." if not error else "x", end="", flush=True)
        print()

    return report


def render(report) -> None:
    """Print the measurement. Nothing here computes; it only formats."""
    labels = report.labels

    if not labels:
        print(f"\n{YELLOW}No ASR adapter was reachable, so there is nothing to "
              f"compare.{RESET}")
        print(f"{DIM}This is a valid outcome, not a failure: every adapter was "
              f"skipped for a stated reason above.\nFor a credential-free "
              f"comparison install the local pair:{RESET}")
        print(f"{DIM}    uv sync --prerelease=allow --extra local-asr{RESET}")
        print(f"{DIM}Vosk additionally needs a model — see integrations.yml "
              f"`model_path`.{RESET}\n")
        return

    # -- latency ------------------------------------------------------------
    print(f"\n{BOLD}Latency per utterance (ms){RESET}")
    print(f"  {'adapter':<18} {'n':>3} {'min':>8} {'median':>8} {'p95':>8} {'max':>8}")
    for label in labels:
        d = report.latency(label)
        if not d:
            print(f"  {label:<18} {'—':>3} {'no successful call':>36}")
            continue
        print(f"  {label:<18} {int(d['n']):>3} {d['min']:>8.0f} "
              f"{d['median']:>8.0f} {d['p95']:>8.0f} {d['max']:>8.0f}")

    # -- agreement ----------------------------------------------------------
    print(f"\n{BOLD}Inter-vendor agreement{RESET} "
          f"{DIM}(1.00 = identical after normalisation){RESET}")
    if len(labels) < 2:
        print(f"  {YELLOW}Only one adapter ran, so there is no pair to compare."
              f"{RESET}")
        print(f"  {DIM}Agreement is a relative measure; it needs at least two "
              f"independent vendors.{RESET}")
    else:
        matrix = report.agreement_matrix()
        print(f"  {'':<18}" + "".join(f"{l[:10]:>11}" for l in labels))
        for left in labels:
            cells = "".join(
                f"{v:>11.2f}" if (v := matrix[(left, right)]) is not None
                else f"{'—':>11}"
                for right in labels
            )
            print(f"  {left:<18}{cells}")

        print(f"\n{BOLD}Disagreement hotspots{RESET} "
              f"{DIM}(worst first — the audio worth listening to){RESET}")
        hotspots = report.disagreement_hotspots()
        if not hotspots:
            print(f"  {DIM}No fixture was heard by two or more adapters.{RESET}")
        for name, score in hotspots:
            bar = "█" * int(round(score * 20))
            print(f"  {name:<18} {score:>5.2f}  {bar}")

    # -- accuracy, only where a reference exists ----------------------------
    if report.has_references:
        print(f"\n{BOLD}Word error rate{RESET} "
              f"{DIM}(against the corpus reference transcripts){RESET}")
        for label in labels:
            wer = report.wer(label)
            print(f"  {label:<18} " +
                  (f"{wer:>6.2%}" if wer is not None else f"{'—':>6}"))
    else:
        # Deliberate: no column, no placeholder, no zero.
        print(f"\n{DIM}No fixture carries a reference transcript, so no word "
              f"error rate is reported.{RESET}")

    print(f"\n{DIM}These numbers describe this corpus on this machine. They are "
          f"a measurement,\nnot a vendor ranking: six synthetic utterances "
          f"cannot tell you which vendor is\nbest on your callers' audio. Point "
          f"the corpus at your own recordings for that.{RESET}\n")


def _quieten() -> None:
    """Keep the report readable.

    Two sources of noise, neither of them a result: the engines' own INFO/DEBUG
    logging, and a numpy warning from faster-whisper's mel filterbank when a
    frame is pure digital silence (log of zero). The warm-up clip is exactly
    such silence, so this is expected rather than a defect being hidden.
    """
    import logging
    import warnings

    logging.getLogger().setLevel(logging.WARNING)
    for name in ("faster-whisper", "vosk", "voicerouter", "rasa"):
        logging.getLogger(name).setLevel(logging.WARNING)
    warnings.filterwarnings("ignore", message=".*encountered in matmul.*")

    try:
        import structlog

        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
        )
    except Exception:  # noqa: BLE001 - logging setup must not break the bench
        pass


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--include-cloud", action="store_true",
        help="also benchmark configured cloud vendors (makes billable calls)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    _quieten()

    # The default run must not be able to spend money even by accident, so the
    # credentials `make probe` loads from .env are deliberately not loaded here
    # unless cloud vendors were explicitly asked for.
    if args.include_cloud:
        from probe_providers import _load_env

        _load_env()

    report = asyncio.run(run_bench(args.include_cloud))
    render(report)
    # Skipped adapters are an expected outcome, never a failure. The benchmark
    # reports what it could measure and exits clean.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
