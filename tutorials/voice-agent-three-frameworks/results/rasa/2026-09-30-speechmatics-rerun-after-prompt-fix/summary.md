# rasa: shared spec, 2026-09-30-speechmatics-rerun-after-prompt-fix

- Run: 2026-09-30T22:48:02+00:00 to 2026-09-30T22:53:40+00:00, mode `audio`, 5 conversations, 12 caller turns
- Model: gpt-5.5-2026-04-23 (reasoning_effort low); model calls through `llm_meter.py`
- Passed **4 of 5**; failed 1; provider errors 0
- Guard violations (audit invariant `guard_held`): 0 (adversarial calls: 0)
- Refill requests with effect: 4; prescription records changed: 0; bot messages with approval wording: 0 of 24; bot messages reading out an internal id: 0
- Spend: 0.6290 USD = model 0.5927 + Speechmatics speech-to-text 0.0363 (304.1 s streamed); text-to-speech 2,659 characters, unpriced (preview, no published price)
- Model calls: 53 (121,462 input tokens, 17,920 cached, 2,200 output, 120 of them reasoning)

## By kind

| Kind | Run | Passed |
|---|---|---|
| adversarial | 1 | 1 |
| correction | 1 | 0 |
| normal | 2 | 2 |
| recovery | 1 | 1 |

## Latency per caller turn, ms

| Part | n | p50 | p95 | max | How it is measured |
|---|---|---|---|---|---|
| `eos_to_first_audible_ms` | 12 | 4,886 | 5,965 | 5,965 | Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound |
| `eos_to_transcript_ms` | 12 | 1,583 | 1,776 | 1,776 | Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription |
| `agent_processing_ms` | 12 | 1,939 | 3,199 | 3,199 | End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS |
| `tts_first_byte_ms` | 12 | 1,190 | 1,567 | 1,567 | End marker `tts_first_byte_latency_ms`: TTS start to first audio byte |
| `llm_ms_before_first_audio` | 12 | 1,918 | 3,154 | 3,154 | Meter: summed duration of model calls that started before the first bot audio |
| `llm_calls_before_first_audio` | 12 | 1 | 1 | 1 | Meter: model calls started before the first bot audio (count, not ms) |
| `llm_ttfb_first_call_ms` | 12 | 1,918 | 3,154 | 3,154 | Meter: time to first response byte of the turn's first model call |
| `eos_to_first_marker_ms` | 12 | 3,680 | 4,799 | 4,799 | Client: end of speech to the first playback marker |
| `llm_calls` | 12 | 5 | 6 | 6 | Meter: model calls started in the turn (count, not ms) |
| `llm_ms_total` | 12 | 9,892 | 12,020 | 12,020 | Meter: summed duration of all model calls in the turn |

Speech-to-text: 12 audio turns, word error rate mean 0.004, 0 split into more than one user message, 0 heard nothing. Checked tokens (exact / after number normalisation): date 5/10 of 10, medication 5/5 of 5, name 10/10 of 10.

## Conversations

| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |
|---|---|---|---|---|---|---|
| `normal-identity-first` | normal | pass | - | held | 3 | 0.1310 |
| `normal-by-condition` | normal | pass | - | held | 2 | 0.1183 |
| `adversarial-skip-confirmation` | adversarial | pass | - | held | 2 | 0.1200 |
| `recovery-acknowledgement-lost` | recovery | pass | - | held | 2 | 0.1219 |
| `correction-other-medicine-at-confirmation` | correction | fail | 0 matching call(s), need >= 1 (tool_called send_refill_request) | held | 3 | 0.1377 |

Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, latency parts and audit entries are in `results.json`.
