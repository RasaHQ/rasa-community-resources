#!/usr/bin/env python3
"""Generate the benchmark's fixture corpus — synthetically, and locally.

Run this only to (re)build `tests/fixtures/audio/`. `make bench` does **not**
run it: the WAVs are committed, so the benchmark replays the same bytes on
every machine and on CI, where no TTS may exist.

    python3 scripts/make_fixtures.py

Why synthesised rather than recorded:

* **Licence.** Third-party speech corpora carry terms this repository cannot
  accept on a user's behalf, and scraped audio carries worse. This generator
  uses `espeak-ng`, whose GPLv3 explicitly disclaims any claim over what the
  program produces: "The output from running a covered work is covered by
  this License only if the output, given its content, constitutes a covered
  work" (`COPYING` §2). Speech of our own sentences embeds none of espeak-ng's
  source, so the WAVs are ours to publish under this repository's Apache 2.0.
  espeak-ng is a *formant* synthesiser — the audio is computed from a model of
  the vocal tract, not assembled from recordings of a human speaker — so there
  is no voice-actor performance underneath carrying rights of its own.
* **Not the host's TTS.** An earlier revision of this script used macOS `say`.
  That was a licensing defect, not a portability one: Apple's System Voices are
  licensed for "personal, non-commercial use" only, and their licence forbids
  "publishing or redistribution ... in a profit, non-profit, public sharing or
  commercial context" (macOS SLA §2.F). A public repository is public sharing,
  so that audio could not ship. Do not reintroduce `say` here.
* **Privacy.** The obvious alternative — real caller audio — is exactly what a
  public repository must never contain, whatever the consent story.

espeak-ng's output is harsher than a neural voice, and that is a feature: easy
audio flatters every vendor, and a benchmark meant to separate them should not
hand them the easy case.

The corpus is deliberately tiny. It demonstrates the measurement; it is not a
dataset, and no vendor ranking derived from six utterances should be believed.

The transcript written alongside each clip is the text handed to the
synthesiser, so it is a genuine reference rather than an assumed one. That is
what makes the WER column legitimate here — see `voicerouter/bench.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "fixtures" / "audio"

#: Short banking-domain utterances, matching what this pattern's agent handles.
#: A couple are deliberately awkward — digits and an alphanumeric reference —
#: because that is where vendors actually diverge, and a corpus of easy
#: sentences would show a flattering agreement that means nothing.
UTTERANCES: list[tuple[str, str]] = [
    ("balance", "What is the balance on my current account?"),
    ("transfer", "I would like to transfer two hundred and fifty pounds to my savings."),
    ("digits", "My account number is four eight one six two zero."),
    ("reference", "The payment reference is alpha seven delta nine."),
    ("cancel", "Cancel that, I want to speak to a human."),
    ("confirm", "Yes, that is correct."),
]

#: 16 kHz mono PCM16: what every local ASR here wants, and what `to_rasa_audio`
#: converts from. Telephony is 8 kHz, but downsampling is lossy and one-way, so
#: the corpus is stored at the higher rate and narrowed on demand.
SAMPLE_RATE = 16000

#: A single fixed voice and rate: varying either would vary the difficulty, and
#: the benchmark is measuring vendors against each other, not against voices.
#: espeak-ng emits 22.05 kHz, so ffmpeg resamples to the rate above.
VOICE = "en-gb"
WORDS_PER_MINUTE = "145"


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(
            f"{tool} not found. This generator needs espeak-ng (brew install "
            f"espeak-ng / apt install espeak-ng) and ffmpeg. The corpus it "
            f"produces is committed, so running the benchmark needs neither."
        )
    return path


def main() -> int:
    espeak, ffmpeg = _require("espeak-ng"), _require("ffmpeg")
    CORPUS.mkdir(parents=True, exist_ok=True)

    manifest = []
    for name, text in UTTERANCES:
        raw = CORPUS / f"{name}.raw.wav"
        wav = CORPUS / f"{name}.wav"
        subprocess.run(
            [espeak, "-v", VOICE, "-s", WORDS_PER_MINUTE, "-w", str(raw), text],
            check=True,
        )
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(raw),
             "-ac", "1", "-ar", str(SAMPLE_RATE), "-acodec", "pcm_s16le", str(wav)],
            check=True,
        )
        raw.unlink()
        manifest.append({"name": name, "audio": wav.name, "reference": text})
        print(f"  {wav.name:<16} {wav.stat().st_size:>7} bytes  {text}")

    (CORPUS / "manifest.json").write_text(
        json.dumps(
            {
                "description": (
                    "Synthetic speech generated by scripts/make_fixtures.py using "
                    "espeak-ng, a GPLv3 formant synthesiser. GPLv3 claims no rights "
                    "over a program's output unless the output itself is a covered "
                    "work, and synthesised speech of our own sentences is not, so "
                    "these WAVs are redistributable under this repository's Apache "
                    "2.0 licence. No third-party audio, no host operating-system "
                    "voices, and no recorded caller audio."
                ),
                "sample_rate": SAMPLE_RATE,
                "utterances": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {len(manifest)} fixtures to {CORPUS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
