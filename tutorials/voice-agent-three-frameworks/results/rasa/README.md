# Recorded runs: the Rasa Mantle version

On 2026-09-30 and 2026-10-01 (UTC), one Mac, `gpt-5.5-2026-04-23` at `reasoning_effort: low`,
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
| `2026-10-01-smoke-text-call-purposes/` | One typed call to try the call-purpose labelling (its labels came out as `other`: the first version walked the call stack, which Mantle's task boundary cuts; the headline run uses a context variable instead) | 1 | 1 | 0.11 |
| `2026-10-01-speechmatics-live-shared-prompt/` | **The headline:** all 17 calls over browser audio on the shared procedure, with `call-purposes.jsonl` (each model call labelled by the Mantle function that made it) | 17 | 16 | 2.01 |
| `2026-10-01-guard-off-adversarial/` | The 6 adversarial calls against the guard-off baseline (`rasa/guard.diff` reversed in a temporary copy) | 6 | 6 (0 guard violations) | 0.48 |

`spend-ledger.json` lists every run: 5.31 USD recorded, 5.56 USD with the
unmetered page check's estimate. The first phase (through the page check)
was 2.71 USD recorded against a 4 USD cap; the comparison phase added 2.60
USD against a 3 USD budget shared with the LangGraph guard-off run (0.21,
in `../langgraph/spend-ledger.json`).

`python3 ../../shared/spec/rasa_call_breakdown.py <run>` shows where a run's
model calls went.
