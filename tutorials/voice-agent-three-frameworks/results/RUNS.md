# How the 2026-10-01 follow-up runs were launched

The commands below are the ones that produced the run folders named, typed
from the tutorial folder (`tutorials/voice-agent-three-frameworks/`) on the
same Mac as the earlier runs, on 2026-10-01 between 12:08 and 13:38 UTC.
Keys came from the repository-root `.env`. Every run was appended to its
framework's `spend-ledger.json`.

## The harder adversarial set, second run (guard on and guard off)

Guard on, from the shipped folders:

```bash
python3 shared/spec/run_spec.py langgraph --spec shared/spec/conversations-adversarial-2.json \
  --server-cmd "uv run --locked python server.py --port {port}" \
  --label 2026-10-01-adversarial-2-run2 --budget-usd 0.40
python3 shared/spec/run_spec.py strands --spec shared/spec/conversations-adversarial-2.json \
  --server-cmd "uv run --locked python server.py --port {port}" \
  --label 2026-10-01-adversarial-2-run2 --budget-usd 0.40
python3 shared/spec/run_spec.py rasa --spec shared/spec/conversations-adversarial-2.json \
  --label 2026-10-01-adversarial-2-run2 --budget-usd 0.90
# Rasa's run stopped at its cap before the sixth call, which then ran alone:
python3 shared/spec/run_spec.py rasa --spec shared/spec/conversations-adversarial-2.json \
  --only hard-ambiguous-early-yes --label 2026-10-01-adversarial-2-run2-ambiguous --budget-usd 0.25
```

Guard off. The copies were made before any `.venv` existed in the shipped
folders, so `cp -R` copied no environment; `uv run --locked` created one in
each copy. Rasa needs no `--no-train` and no separate train step: the
runner's Rasa preset runs `uv run --locked rasa train` in the `--server-cwd`
folder before it starts the server.

```bash
cp -R langgraph langgraph-guard-off
cd langgraph-guard-off && patch -R -E -p1 < guard.diff && cd ..
cp -R strands strands-guard-off
cd strands-guard-off && patch -R -E -p1 < guard.diff && cd ..
cp -R rasa rasa-guard-off
cd rasa-guard-off && patch -R -E -p1 < guard.diff && cd ..

python3 shared/spec/run_spec.py langgraph \
  --spec shared/spec/conversations-adversarial-2.json \
  --server-cmd "uv run --locked python server.py --port {port}" \
  --server-cwd langgraph-guard-off --label 2026-10-01-adversarial-2-guard-off-run2 --budget-usd 0.40
python3 shared/spec/run_spec.py strands \
  --spec shared/spec/conversations-adversarial-2.json \
  --server-cmd "uv run --locked python server.py --port {port}" \
  --server-cwd strands-guard-off --label 2026-10-01-adversarial-2-guard-off-run2 --budget-usd 0.40
python3 shared/spec/run_spec.py rasa \
  --spec shared/spec/conversations-adversarial-2.json \
  --server-cwd rasa-guard-off --label 2026-10-01-adversarial-2-guard-off-run2 --budget-usd 0.85

rm -rf langgraph-guard-off strands-guard-off rasa-guard-off
```

The three guard-on runs and the LangGraph and Strands guard-off runs
overlapped in time, as the first runs did; none of them is used for
latency.

## Rasa with Speechmatics speech-to-text and Deepgram text-to-speech

```bash
make spec-rasa-variant VARIANT=deepgram-tts LABEL=2026-10-01-deepgram-tts-streaming BUDGET=2.45
```

which copies `rasa/` to `rasa-deepgram-tts/` (no `.venv`, models or `.env`),
puts `variants/rasa-deepgram-tts.integrations.yml` there as
`integrations.yml`, and runs

```bash
python3 shared/spec/run_spec.py rasa --server-cwd rasa-deepgram-tts \
  --speech-prices shared/spec/speech-prices/speechmatics-stt-deepgram-tts.json \
  --label 2026-10-01-deepgram-tts-streaming --budget-usd 2.45
```

## Deepgram speech in and out, all three

One-call smoke runs first, which may run together:

```bash
make rasa-variant VARIANT=deepgram
python3 shared/spec/run_spec.py rasa --server-cwd rasa-deepgram \
  --speech-prices shared/spec/speech-prices/deepgram.json \
  --only normal-lisinopril --label 2026-10-01-deepgram-smoke --budget-usd 0.30
python3 shared/spec/run_spec.py langgraph \
  --server-cmd "uv run --locked python ../shared/speech-deepgram/launch.py server.py --port {port}" \
  --speech-prices shared/spec/speech-prices/deepgram.json \
  --only normal-lisinopril --label 2026-10-01-deepgram-smoke --budget-usd 0.20
python3 shared/spec/run_spec.py strands \
  --server-cmd "uv run --locked python ../shared/speech-deepgram/launch.py server.py --port {port}" \
  --speech-prices shared/spec/speech-prices/deepgram.json \
  --only normal-lisinopril --label 2026-10-01-deepgram-smoke --budget-usd 0.20
```

Then the 17 calls, one framework at a time and nothing else running, after
the Rasa streaming-TTS run above:

```bash
make spec-rasa-variant VARIANT=deepgram LABEL=2026-10-01-deepgram-live BUDGET=2.6
make spec-deepgram FW=langgraph LABEL=2026-10-01-deepgram-live BUDGET=1.0
make spec-deepgram FW=strands LABEL=2026-10-01-deepgram-live BUDGET=1.0
```

`make spec-deepgram` runs `run_spec.py <framework>` with
`--server-cmd "uv run --locked python ../shared/speech-deepgram/launch.py server.py --port {port}"`
and `--speech-prices shared/spec/speech-prices/deepgram.json`. The launcher
starts the shipped `server.py` with `cedar_speech_deepgram`'s classes in
place of `cedar_speech`'s Speechmatics ones; no file in `langgraph/` or
`strands/` changes.

`rasa-deepgram-tts/` and `rasa-deepgram/` are temporary copies (ignored by
git) and were deleted after the runs.
