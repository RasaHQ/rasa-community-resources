# strands: shared spec, 2026-10-01-deepgram-smoke

- Run: 2026-10-01T12:13:32+00:00 to 2026-10-01T12:14:24+00:00, mode `audio`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.0549 USD = model 0.0349 + Deepgram speech-to-text 0.0063 (49.2 s streamed) + Deepgram text-to-speech 0.0137 (456 characters of bot text at 0.03 USD per 1,000)
- Model calls: 4 (6,185 input tokens, 0 cached, 134 output, 11 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| normal | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 1,369 | 3,205 | 3,205 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 668 | 685 | 685 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 2.5 | 1,724 | 1,724 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 686 | 792 | 792 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 1,255 | 2,249 | 2,249 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 2 | 2 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 518 | 590 | 590 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 1,369 | 3,205 | 3,205 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 1 | 3 | 3 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 1,255 | 3,526 | 3,526 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 2 audio turns, word error rate mean 0.071, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 2/2 of 2, medication 1/1 of 1, name 2/2 of 2.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-lisinopril` | normal | pass | - | held | 2 | 0.0549 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
