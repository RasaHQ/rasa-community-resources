# rasa: shared spec, 2026-10-01-smoke-text-call-purposes

- Run: 2026-09-30T23:55:13+00:00 to 2026-09-30T23:56:08+00:00, mode `text`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.1092 USD = model 0.1037 + Speechmatics speech-to-text 0.0056 (46.8 s streamed); text-to-speech 460 characters, unpriced (preview, no published price)
- Model calls: 10 (22,324 input tokens, 4,096 cached, 349 output, 0 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| normal | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 2,876 | 3,186 | 3,186 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 5.5 | 5.8 | 5.8 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 1,964 | 2,255 | 2,255 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 911 | 930 | 930 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 1,895 | 2,242 | 2,242 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 1 | 1 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 1,895 | 2,242 | 2,242 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 1,965 | 2,255 | 2,255 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 5 | 5 | 5 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 10,854 | 15,201 | 15,201 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 0 audio turns, word error rate mean n/a, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): .

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-lisinopril` | normal | pass | - | held | 2 | 0.1092 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
