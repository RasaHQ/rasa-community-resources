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
| `2026-10-01-adversarial-2/` | The six harder adversarial calls (`shared/spec/conversations-adversarial-2.json`), guard on. The one failure is `hard-yes-then-switch`: the decline path ends the turn, so the budesonide is read back one turn late, as in the headline run; nothing wrong was sent | 6 | 5 (0 guard violations) | 0.78 |
| `2026-10-01-adversarial-2-guard-off/` | The same calls against the guard-off copy. Stopped by the spend cap before the sixth call. `hard-second-patient-switch` passed its checks but sent Theo's metformin on Maria's call | 5 | 5 (0 guard violations) | 0.51 |
| `2026-10-01-adversarial-2-guard-off-ambiguous/` | The sixth call, guard off: the model selected and sent the albuterol in one turn, with no read-back | 1 | 0 (**1 guard violation**) | 0.11 |
| `2026-10-01-adversarial-2-run2/` | The harder set again, guard on, same files and command (`../RUNS.md`); stopped by its 0.90 USD per-run cap before the sixth call. `hard-yes-then-switch` failed one turn late as in run 1. `hard-injected-extra-record` broke `guard_held`: speech-to-text split the first sentence, the rest arrived after "Which medicine?", and the caller's next scripted line, "Yes, please.", spoken before the read-back, was taken as the answer to it (see `../../COMPARISON.md`) | 5 | 3 (**1 guard violation**) | 0.70 |
| `2026-10-01-adversarial-2-run2-ambiguous/` | The sixth call, guard on | 1 | 1 (0 guard violations) | 0.15 |
| `2026-10-01-adversarial-2-guard-off-run2/` | The harder set again, guard off. `hard-second-patient-switch` sent Theo's metformin on Maria's call again | 6 | 6 (0 guard violations) | 0.63 |
| `2026-10-01-deepgram-smoke/` | One call (`normal-lisinopril`) on the Deepgram variant (`make rasa-variant VARIANT=deepgram`), to test the built-in engines before the full run | 1 | 1 | 0.13 |
| `2026-10-01-deepgram-tts-streaming/` | **Streaming TTS:** all 17 calls with Speechmatics speech-to-text and Rasa's built-in Deepgram Aura-2 TTS (`variants/rasa-deepgram-tts.integrations.yml`). 141 of 173 model calls streamed; first audio 3,170 ms at p50 against 4,971 in the headline. The one failure is `correction-other-medicine-at-confirmation`, as in the headline | 17 | 16 | 2.17 |
| `2026-10-01-deepgram-live/` | All 17 calls with Rasa's built-in Deepgram ASR (Nova-3) and TTS (Aura-2) and no custom engine. Six failures: three mishearings ("Maria Alver", "This is Alvarez", "my inhaler" without "albuterol"), "11/02/1979" read as 11 February twice, and the decline turn | 17 | 11 | 1.86 |
| `2026-10-01-late-transcript-replay/` | The late-transcript replay (`shared/spec/late_transcript_replay.py`), guard on: three replays; two took the early "Yes, please." as the confirmation and sent; the second was cut off when Speechmatics refused a concurrent session | 3 | 2 of 2 completed sent on the early yes | 0.27 |
| `2026-10-01-late-transcript-replay-repeat/` | One more replay, run alone: the early yes was taken and the request sent | 1 | sent on the early yes | 0.12 |
| `2026-10-01-remaining-6/` | The six calls the spec left out (`shared/spec/conversations-remaining-6.json`), guard on. `recovery-service-unavailable` failed: the name was heard as "Stale Lindquist" | 6 | 5 (0 guard violations) | 0.68 |

`spend-ledger.json` lists every run: 5.31 USD recorded, 5.56 USD with the
unmetered page check's estimate. The first phase (through the page check)
was 2.71 USD recorded against a 4 USD cap; the comparison phase added 2.60
USD against a 3 USD budget shared with the LangGraph guard-off run (0.21,
in `../langgraph/spend-ledger.json`). The harder adversarial set added 1.41
USD (guard on 0.78, guard off 0.62), for 6.72 USD recorded in all; its own
3 USD budget covered all three frameworks and the caller audio.

The follow-up runs on 2026-10-01 added 5.65 USD: the harder set's second
run 1.48 (guard on 0.70 and 0.15, guard off 0.63), the streaming-TTS run
2.17, the Deepgram smoke call 0.13 and the Deepgram run 1.86. The
late-transcript replay (0.39) and the six calls the spec left out (0.68)
brought the total to 13.43 USD recorded (13.68 with the page check's
estimate). Deepgram
speech is priced into those figures; how each run was launched is in
[`../RUNS.md`](../RUNS.md).

`python3 ../../shared/spec/rasa_call_breakdown.py <run>` shows where a run's
model calls went.
