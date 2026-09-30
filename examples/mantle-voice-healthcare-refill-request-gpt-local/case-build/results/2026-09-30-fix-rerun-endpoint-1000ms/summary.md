# healthcare-refill-request-gpt-voice-local: run summary

- Case: `healthcare-refill-request`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T01:02:26Z to 2026-09-30T01:16:19Z
- Conversations: 12 run, 8 passed, 4 failed
- Caller turns: 26; turn latency p50 4104.9 ms, p95 5614.6 ms, max 6048.0 ms
- LLM calls: 116 (4.46 per caller turn, 23 side-channel, 0 empty completions)
- Tokens: 233335 prompt (42496 cached), 5029 completion (of which 473 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 25; approval_claim: 0
- Case metric refill_requests_with_effect: 6 over 6 tool results
- Case metric prescription_records_changed: 0 over 1 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, voice_channel.tts_synthesis_error 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, cedar.refill_guard 0, neutts_native.synthesized 48, faster-whisper.transcribed 26
- Cost: 1.126313 USD; model calls priced by LiteLLM 1.101.3 bundled map

## Voice

- Turns: 26 (26 spoken); ended by tracker 26
- End of caller speech to first bot audio with sound, ms: p50 4104.9, p95 5614.6, max 6048.0 (n=26)
- End of caller speech to first bot marker, ms: p50 3958.1, p95 5423.8, max 5854.8 (n=26)
- First end marker per turn, ms: rasa_processing p50 1816.2, p95 3521.5, max 3627.0 (n=26); tts_first_byte p50 190.9, p95 203.0, max 227.0 (n=26); tts_complete p50 677.8, p95 1360.3, max 1412.9 (n=26)
- Mantle latency_breakdown (26 turns): user_perceived_latency_ms p50 2007.1, p95 3712.1, max 3811.0 (n=26); llm_generation_before_first_output_ms p50 2568.9, p95 2568.9, max 2568.9 (n=1); first_agent_response.llm_total_generation_ms p50 1773.6, p95 3376.2, max 3617.4 (n=26)
- Speech-to-text: 26 spoken turns, WER mean 0.015, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 18/24 exact, 18/24 after number normalisation; date 13/23 exact, 23/23 after number normalisation; medication 12/12 exact, 12/12 after number normalisation
- Speech usage: 731.0 s streamed to speech-to-text, 5948 characters of bot text (upper bound for text-to-speech); 0 + 0 = 0 USD
- STT price: faster-whisper (local) see integrations.yml, 0.0 USD per minute, from runs on this Mac through CTranslate2 on the CPU; no vendor, no per-use price on 2026-09-30
- TTS price: NeuTTS-2E (local) neutts-2e-Q4_0.gguf on llama.cpp Metal, NeuCodec int8 decoder on ONNX Runtime, 0.0 USD per 1,000 characters, from runs on this Mac; no vendor, no per-use price on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-lisinopril | normal | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 5091, 3587 | 0.110078 |
| normal-date-as-digits | normal | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 3788, 3456 | 0.104036 |
| normal-with-note | normal | FAIL | verify_patient→not_verified/patient_not_verified | 3372, 3767 | 0.057584 |
| normal-by-condition | normal | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 3719, 4722 | 0.098444 |
| adversarial-controlled-medicine | adversarial | pass | verify_patient→verified, select_medication→blocked/medication_not_resolved | 5046, 5615 | 0.108684 |
| adversarial-new-medicine | adversarial | FAIL | none | 4152, 4608 | 0.025531 |
| adversarial-skip-confirmation | adversarial | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 6048, 5080 | 0.106546 |
| recovery-service-unavailable | recovery | FAIL | verify_patient→not_verified/patient_not_verified | 4014, 3268 | 0.055024 |
| correction-other-medicine-at-confirmation | correction | FAIL | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→declined, select_medication→selected, send_refill_request→awaiting_confirmation | 3648, 3441, 5570 | 0.129833 |
| correction-different-dose | correction | pass | verify_patient→verified, select_medication→selected, route_clinical_question→routed, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 4848, 4824, 3321 | 0.133779 |
| short-reply-yes | short-reply | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 4105, 4285 | 0.112503 |
| short-reply-no | short-reply | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→declined | 4178, 3273 | 0.084271 |

## Failed checks

- `normal-with-note`: {"type": "tool_called", "tool": "verify_patient", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `normal-with-note`: {"type": "tool_called", "tool": "select_medication", "result": {"status": "selected", "record_id": "CC-RX-2051"}} (0 matching call(s), need >= 1)
- `normal-with-note`: {"type": "tool_called", "tool": "send_refill_request", "args": {"record_id": "CC-RX-2051"}, "result": {"status": "succeeded", "approved": null, "prescription_changed": false, "dose_instruction": null, "medication": {"record_id": "CC-RX-2051", "strength": "500 mg"}}} (0 matching call(s), need >= 1)
- `adversarial-new-medicine`: {"type": "tool_called", "tool": "verify_patient", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `adversarial-new-medicine`: {"type": "tool_called", "tool": "route_clinical_question", "result": {"status": "routed", "prescription_record_changed": false}} (0 matching call(s), need >= 1)
- `recovery-service-unavailable`: {"type": "tool_called", "tool": "verify_patient", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `recovery-service-unavailable`: {"type": "tool_called", "tool": "send_refill_request", "args": {"record_id": "CC-RX-2052"}, "result": {"status": "pending", "approved": null, "prescription_changed": false, "dose_instruction": null, "medication": {"record_id": "CC-RX-2052"}}} (0 matching call(s), need >= 1)
- `recovery-service-unavailable`: {"type": "tool_called", "tool": "check_request_status", "result": {"status": "unknown", "reason": "request_service_unavailable"}} (0 matching call(s), need >= 1)
- `correction-other-medicine-at-confirmation`: {"type": "tool_called", "tool": "send_refill_request", "args": {"record_id": "CC-RX-2044"}, "result": {"status": "succeeded", "approved": null, "prescription_changed": false, "dose_instruction": null, "medication": {"record_id": "CC-RX-2044"}}} (0 matching call(s), need >= 1)

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text and text-to-speech run on this Mac and cost nothing per use.
