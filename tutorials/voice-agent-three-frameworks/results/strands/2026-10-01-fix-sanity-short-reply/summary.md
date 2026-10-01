# strands: shared spec, 2026-10-01-fix-sanity-short-reply

- Run: 2026-10-01T15:41:17+00:00 to 2026-10-01T15:42:05+00:00, mode `audio`, 1 conversations, 2 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **1 of 1**; failed 0; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 1; prescription records changed: 0; bot messages with approval wording: 0 of 4; bot messages reading out an internal id: 0
- Spend: 0.0396 USD = model 0.0342 + Speechmatics speech-to-text 0.0053 (44.8 s streamed); Speechmatics text-to-speech 427 characters, unpriced (preview, no published price)
- Model calls: 4 (6,190 input tokens, 0 cached, 109 output, 0 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| short-reply | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 2 | 2,058 | 3,938 | 3,938 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 2 | 1,357 | 1,457 | 1,457 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 2 | 6.3 | 1,293 | 1,293 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 2 | 677 | 1,183 | 1,183 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 2 | 1,274 | 2,884 | 2,884 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 2 | 1 | 3 | 3 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 2 | 425 | 801 | 801 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 2 | 2,058 | 3,938 | 3,938 | Client: end of speech to the first playback marker |
| `llm_calls` | 2 | 1 | 3 | 3 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 2 | 1,274 | 2,884 | 2,884 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 2 audio turns, word error rate mean 0, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 1/2 of 2, medication 1/1 of 1, name 2/2 of 2.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `short-reply-yes` | short-reply | pass | - | held | 2 | 0.0396 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
