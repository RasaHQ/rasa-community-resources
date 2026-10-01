# rasa: shared spec, 2026-10-01-fix-sanity-short-reply

- Run: 2026-10-01T15:41:10+00:00 to 2026-10-01T15:42:17+00:00, mode `audio`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.1226 USD = model 0.1154 + Speechmatics speech-to-text 0.0072 (60.0 s streamed); Speechmatics text-to-speech 487 characters, unpriced (preview, no published price)
- Model calls: 10 (22,372 input tokens, 1,536 cached, 348 output, 0 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| short-reply | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 4,653 | 5,141 | 5,141 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 1,206 | 1,676 | 1,676 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 2,123 | 2,446 | 2,446 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 1,012 | 1,348 | 1,348 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 2,033 | 2,406 | 2,406 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 1 | 1 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 2,033 | 2,406 | 2,406 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 3,639 | 3,790 | 3,790 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 5 | 5 | 5 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 9,853 | 12,905 | 12,905 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 2 audio turns, word error rate mean 0, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 1/2 of 2, medication 1/1 of 1, name 2/2 of 2.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `short-reply-yes` | short-reply | pass | - | held | 2 | 0.1226 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
