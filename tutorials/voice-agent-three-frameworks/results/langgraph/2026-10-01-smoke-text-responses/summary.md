# langgraph: shared spec, 2026-10-01-smoke-text-responses

- Run: 2026-09-30T23:17:27+00:00 to 2026-09-30T23:18:08+00:00, mode `text`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.0390 USD = model 0.0344 + Speechmatics speech-to-text 0.0046 (38.1 s streamed); text-to-speech 454 characters, unpriced (preview, no published price)
- Model calls: 5 (6,095 input tokens, 0 cached, 131 output, 0 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| normal | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 479 | 2,223 | 2,223 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 0.1 | 0.1 | 0.1 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 0.3 | 1,340 | 1,340 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 478 | 883 | 883 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 1,964 | 3,235 | 3,235 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 2 | 2 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 559 | 917 | 917 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 479 | 2,223 | 2,223 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 2 | 3 | 3 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 3,171 | 4,280 | 4,280 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 0 audio turns, word error rate mean n/a, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): .

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-lisinopril` | normal | pass | - | held | 2 | 0.0390 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
