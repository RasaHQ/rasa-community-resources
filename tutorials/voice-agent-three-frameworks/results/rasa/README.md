# Recorded runs: the Rasa Mantle version

Recorded on 2026-09-30 and 2026-10-01 (UTC) on one Mac, with
`gpt-5.5-2026-04-23` at reasoning effort low. Most folders were produced by
`shared/spec/run_spec.py` or `shared/spec/late_transcript_replay.py`, and the
commands for the later runs are in [`../RUNS.md`](../RUNS.md).

A run folder holds:

- `summary.md`: read this first;
- `results.json`;
- `audit.jsonl`: the clinic's audit log, which decides each call;
- `llm-calls.jsonl`: the meter's record of each model call;
- `events/`: the agent's own conversation record.

`spend-ledger.json` records every run.

| Folder | What it holds |
|---|---|
| `2026-09-30-smoke-text-neutts/` | A typed-turn smoke test of the harness, before the switch to Speechmatics |
| `2026-09-30-smoke-text-speechmatics/` | A typed-turn smoke test with Speechmatics |
| `2026-09-30-speechmatics-live/` | All 17 calls on an earlier wording of the shared procedure (history) |
| `2026-09-30-speechmatics-rerun-after-prompt-fix/` | Five calls again after the procedure was reworded |
| `2026-09-30-web-page-check/` | The shared voice page in headless Chromium (`check-page.json`) |
| `2026-10-01-adversarial-2/` | The six harder adversarial calls (`shared/spec/conversations-adversarial-2.json`), guard on |
| `2026-10-01-adversarial-2-guard-off/` | The six harder calls against the guard-off baseline (`guard.diff` reversed in a temporary copy) |
| `2026-10-01-adversarial-2-guard-off-ambiguous/` | `hard-ambiguous-early-yes` with the guard off, run on its own after the run above reached its per-run cap |
| `2026-10-01-adversarial-2-guard-off-run2/` | The six harder calls, guard off, second run |
| `2026-10-01-adversarial-2-run2/` | The six harder calls, guard on, second run |
| `2026-10-01-adversarial-2-run2-ambiguous/` | `hard-ambiguous-early-yes` with the guard on, run on its own after `-run2` reached its per-run cap |
| `2026-10-01-backchannel-filler/` | Replay: "Okay." during the filler, shipped build |
| `2026-10-01-backchannel-filler-fix/` | The same with `fix.diff` applied |
| `2026-10-01-backchannel-readback/` | Replay: "Yeah." during the read-back, shipped build |
| `2026-10-01-backchannel-readback-fix/` | The same with `fix.diff` applied |
| `2026-10-01-deepgram-live/` | All 17 calls with Deepgram speech-to-text and TTS |
| `2026-10-01-deepgram-smoke/` | One call with Deepgram speech, before the full run |
| `2026-10-01-deepgram-tts-streaming/` | All 17 calls with Speechmatics speech-to-text and the built-in Deepgram TTS (the model streamed into the TTS) |
| `2026-10-01-fix-sanity/` | Headline calls with a normal yes, against the build with `fix.diff` applied |
| `2026-10-01-fix-sanity-short-reply/` | `short-reply-yes` against the build with `fix.diff` applied |
| `2026-10-01-guard-off-adversarial/` | The six adversarial calls against the guard-off baseline |
| `2026-10-01-late-transcript-replay/` | The late-transcript replay (`shared/spec/late_transcript_replay.py`), shipped build |
| `2026-10-01-late-transcript-replay-fix/` | The same against the build with `fix.diff` applied |
| `2026-10-01-late-transcript-replay-fix-3/` | One more replay against the fixed build |
| `2026-10-01-late-transcript-replay-repeat/` | One more replay against the shipped build, run alone |
| `2026-10-01-remaining-6/` | The six further calls from the source build (`shared/spec/conversations-remaining-6.json`) |
| `2026-10-01-smoke-text-call-purposes/` | A typed call to try the call-purpose labels |
| `2026-10-01-speechmatics-live-shared-prompt/` | **The headline:** all 17 calls over browser audio on the shared procedure, with `call-purposes.jsonl` |
| `2026-10-01-wrong-entry-blue/` | Replay: "Of my blue inhaler." with an early yes, shipped build |
| `2026-10-01-wrong-entry-blue-fix/` | The same with `fix.diff` applied |
| `2026-10-01-wrong-entry-inhaler/` | Replay: "Of my inhaler." with an early yes (two inhalers on the record), shipped build |
| `2026-10-01-wrong-entry-inhaler-fix/` | The same with `fix.diff` applied |

`python3 ../../shared/spec/rasa_call_breakdown.py <run>` lists a run's model calls by the Mantle
function that made them.
