# rasa: shared spec, 2026-09-30-smoke-text-speechmatics

- Run: 2026-09-30T22:26:06+00:00 to 2026-09-30T22:26:57+00:00, mode `text`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.1132 USD = model 0.1082 + Speechmatics speech-to-text 0.0050 (41.7 s streamed); text-to-speech 467 characters, unpriced (preview, no published price)
- Model calls: 10 (21,995 input tokens, 3,072 cached, 401 output, 52 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| normal | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 2,615 | 2,653 | 2,653 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 3 | 6.5 | 6.5 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 1,560 | 1,752 | 1,752 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 900 | 1,054 | 1,054 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 1,521 | 1,708 | 1,708 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 1 | 1 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 1,521 | 1,708 | 1,708 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 1,561 | 1,752 | 1,752 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 5 | 5 | 5 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 10,266 | 11,325 | 11,325 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 0 audio turns, word error rate mean n/a, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): .

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-lisinopril` | normal | pass | - | held | 2 | 0.1132 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
