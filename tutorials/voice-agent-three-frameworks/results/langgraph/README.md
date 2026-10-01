# Recorded runs: the LangGraph version

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
| `2026-10-01-adversarial-2/` | The six harder adversarial calls (`shared/spec/conversations-adversarial-2.json`), guard on |
| `2026-10-01-adversarial-2-guard-off/` | The six harder calls against the guard-off baseline (`guard.diff` reversed in a temporary copy) |
| `2026-10-01-adversarial-2-guard-off-run2/` | The six harder calls, guard off, second run |
| `2026-10-01-adversarial-2-run2/` | The six harder calls, guard on, second run |
| `2026-10-01-backchannel-filler/` | Replay: "Okay." during the filler, shipped build |
| `2026-10-01-backchannel-filler-fix/` | The same with `fix.diff` applied |
| `2026-10-01-backchannel-readback/` | Replay: "Yeah." during the read-back, shipped build |
| `2026-10-01-backchannel-readback-fix/` | The same with `fix.diff` applied |
| `2026-10-01-deepgram-live/` | All 17 calls with Deepgram speech-to-text and TTS |
| `2026-10-01-deepgram-smoke/` | One call with Deepgram speech, before the full run |
| `2026-10-01-fix-sanity/` | Headline calls with a normal yes, against the build with `fix.diff` applied |
| `2026-10-01-fix-sanity-short-reply/` | `short-reply-yes` against the build with `fix.diff` applied |
| `2026-10-01-guard-off-adversarial/` | The six adversarial calls against the guard-off baseline |
| `2026-10-01-late-transcript-replay/` | The late-transcript replay (`shared/spec/late_transcript_replay.py`), shipped build |
| `2026-10-01-late-transcript-replay-fix/` | The same against the build with `fix.diff` applied |
| `2026-10-01-remaining-6/` | The six further calls from the source build (`shared/spec/conversations-remaining-6.json`) |
| `2026-10-01-silence-check-in/` | A 50-second call with no caller speech; the check-in was spoken 30 s after the greeting finished playing (`silence-check-in.json`) |
| `2026-10-01-smoke-audio/` | One call over browser audio, before the full run |
| `2026-10-01-smoke-text/` | A typed-turn smoke test on Chat Completions (the model call returned HTTP 400 for function tools with `reasoning_effort`) |
| `2026-10-01-smoke-text-responses/` | The same call on the Responses API |
| `2026-10-01-speechmatics-live/` | **The headline:** all 17 calls over browser audio |
| `2026-10-01-speechmatics-repeat-no-change/` | `recovery-second-verification` again, with nothing changed |
| `2026-10-01-web-page-check/` | The shared voice page in headless Chromium (`check-page.json`) |
| `2026-10-01-wrong-entry-blue/` | Replay: "Of my blue inhaler." with an early yes, shipped build |
| `2026-10-01-wrong-entry-blue-fix/` | The same with `fix.diff` applied |
| `2026-10-01-wrong-entry-inhaler/` | Replay: "Of my inhaler." with an early yes (two inhalers on the record), shipped build |
| `2026-10-01-wrong-entry-inhaler-fix/` | The same with `fix.diff` applied |
