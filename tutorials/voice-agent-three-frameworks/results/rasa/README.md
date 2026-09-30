# Recorded runs: the Rasa Mantle version

All on 2026-09-30, one Mac, `gpt-5.5-2026-04-23` at `reasoning_effort: low`,
rasa-pro 3.21.0.dev5. Produced by `shared/spec/run_spec.py` except where
noted. Each run folder has `summary.md` (read this first), `results.json`,
`audit.jsonl` (the clinic's audit log, which decides pass or fail),
`llm-calls.jsonl` (the meter) and `events/` (Rasa's trackers, for reading).

| Folder | What | Calls | Passed | Spend USD |
|---|---|---|---|---|
| `2026-09-30-smoke-text-neutts/` | Harness smoke test, typed turns, before the switch to Speechmatics (speech was faster-whisper and NeuTTS on the Mac then) | 1 | 1 | 0.13 |
| `2026-09-30-smoke-text-speechmatics/` | Harness smoke test, typed turns, Speechmatics TTS | 1 | 1 | 0.11 |
| `2026-09-30-speechmatics-live/` | **The live run:** all 17 calls over browser audio | 17 | 12 | 1.84 |
| `2026-09-30-speechmatics-rerun-after-prompt-fix/` | The 5 failed calls after the procedure change in commit "Tell the model not to ask its own confirmation question" | 5 | 4 | 0.63 |
| `2026-09-30-web-page-check/` | The shared voice page in headless Chromium through `serve.py` (`check-page.json`); not metered | 2 | handshake, greeting, audio and text round trips all ok | not recorded (estimate 0.25) |

`spend-ledger.json` lists every run: 2.71 USD recorded, 2.96 USD with the
unmetered page check's estimate, against a 4 USD cap.
