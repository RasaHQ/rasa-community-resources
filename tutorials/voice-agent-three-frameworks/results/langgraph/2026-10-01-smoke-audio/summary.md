# langgraph: shared spec, 2026-10-01-smoke-audio

- Run: 2026-09-30T23:18:50+00:00 to 2026-09-30T23:20:07+00:00, mode `audio`, 1 conversations, 3 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 6; bot messages reading out an internal id: 0
- Spend: 0.0530 USD = model 0.0441 + Speechmatics speech-to-text 0.0089 (74.4 s streamed); text-to-speech 673 characters, unpriced (preview, no published price)
- Model calls: 8 (10,119 input tokens, 3,072 cached, 245 output, 40 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| correction | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 3 | 3,791 | 4,656 | 4,656 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 3 | 1,554 | 1,659 | 1,659 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 3 | 1,208 | 1,587 | 1,587 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 3 | 1,155 | 1,409 | 1,409 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 3 | 4,290 | 4,341 | 4,341 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 3 | 2 | 2 | 2 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 3 | 463 | 496 | 496 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 3 | 3,791 | 4,656 | 4,656 | Client: end of speech to the first playback marker |
| `llm_calls` | 3 | 3 | 3 | 3 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 3 | 5,435 | 5,495 | 5,495 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 3 audio turns, word error rate mean 0.033, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 1/2 of 2, medication 2/2 of 2, name 2/2 of 2.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `correction-other-medicine-at-confirmation` | correction | pass | - | held | 3 | 0.0530 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
