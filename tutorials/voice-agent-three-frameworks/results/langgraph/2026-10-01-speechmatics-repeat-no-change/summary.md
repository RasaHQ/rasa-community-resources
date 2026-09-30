# langgraph: shared spec, 2026-10-01-speechmatics-repeat-no-change

- Run: 2026-09-30T23:44:50+00:00 to 2026-09-30T23:45:42+00:00, mode `audio`, 1 conversations, 3 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **0 of 1**; failed 1; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 0; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.0354 USD = model 0.0295 + Speechmatics speech-to-text 0.0059 (49.4 s streamed); text-to-speech 424 characters, unpriced (preview, no published price)
- Model calls: 4 (5,196 input tokens, 0 cached, 119 output, 12 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| recovery | 1 | 0 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 3 | 3,666 | 4,172 | 4,172 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 3 | 1,444 | 1,488 | 1,488 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 3 | 1,010 | 1,273 | 1,273 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 3 | 904 | 1,826 | 1,826 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 3 | 1,912 | 4,206 | 4,206 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 3 | 1 | 2 | 2 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 3 | 448 | 879 | 879 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 3 | 3,666 | 4,172 | 4,172 | Client: end of speech to the first playback marker |
| `llm_calls` | 3 | 1 | 2 | 2 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 3 | 1,912 | 4,206 | 4,206 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 3 audio turns, word error rate mean 0, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 0/2 of 2, medication 1/1 of 1, name 1/1 of 1.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `recovery-second-verification` | recovery | fail | 0 matching call(s), need >= 1 (tool_called verify_patient); 0 matching call(s), need >= 1 (tool_called send_refill_request) | held | 3 | 0.0354 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
