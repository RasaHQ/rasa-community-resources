# langgraph: shared spec, 2026-10-01-smoke-text

- Run: 2026-09-30T23:16:42+00:00 to 2026-09-30T23:17:05+00:00, mode `text`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **0 of 1**; failed 0; provider errors 1
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 0; prescription records changed: 0; bot messages with approval wording: 0 of 2; bot messages reading out an internal id: 0
- Spend: 0.0024 USD = model 0.0000 + Speechmatics speech-to-text 0.0024 (20.1 s streamed); text-to-speech 227 characters, unpriced (preview, no published price)
- Model calls: 2 (0 input tokens, 0 cached, 0 output, 0 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| normal | 1 | 0 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 1,747 | 1,962 | 1,962 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 0.1 | 0.1 | 0.1 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 246 | 492 | 492 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 1,469 | 1,501 | 1,501 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 217 | 486 | 486 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 1 | 1 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 217 | 486 | 486 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 1,747 | 1,962 | 1,962 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 1 | 1 | 1 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 217 | 486 | 486 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 0 audio turns, word error rate mean n/a, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): .

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-lisinopril` | normal | provider_error | 0 matching call(s), need >= 1 (tool_called verify_patient); 0 matching call(s), need >= 1 (tool_called select_medication); 0 matching call(s), need >= 1 (tool_called send_refill_request) | held | 2 | 0.0024 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
