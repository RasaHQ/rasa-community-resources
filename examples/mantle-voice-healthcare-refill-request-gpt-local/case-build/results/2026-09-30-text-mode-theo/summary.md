# healthcare-refill-request-gpt-voice-local: run summary

- Case: `healthcare-refill-request`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T01:28:06Z to 2026-09-30T01:30:09Z
- Conversations: 2 run, 2 passed, 0 failed
- Caller turns: 4; turn latency p50 2227.6 ms, p95 3019.2 ms, max 3019.2 ms
- LLM calls: 21 (5.25 per caller turn, 4 side-channel, 0 empty completions)
- Tokens: 47378 prompt (8704 cached), 1161 completion (of which 89 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 5; approval_claim: 0
- Case metric refill_requests_with_effect: 2 over 2 tool results
- Case metric prescription_records_changed: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, voice_channel.tts_synthesis_error 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, cedar.refill_guard 0, neutts_native.synthesized 11, faster-whisper.transcribed 0
- Cost: 0.232552 USD; model calls priced by LiteLLM 1.101.3 bundled map

## Voice

- Turns: 4 (0 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 2227.6, p95 3019.2, max 3019.2 (n=4)
- End of caller speech to first bot marker, ms: p50 2041.1, p95 2825.2, max 2825.2 (n=4)
- First end marker per turn, ms: rasa_processing p50 2040.8, p95 2825.0, max 2825.0 (n=4); tts_first_byte p50 181.7, p95 194.0, max 194.0 (n=4); tts_complete p50 643.7, p95 732.4, max 732.4 (n=4)
- Mantle latency_breakdown (4 turns): user_perceived_latency_ms p50 2227.2, p95 3018.9, max 3018.9 (n=4); first_agent_response.llm_total_generation_ms p50 2031.2, p95 2820.1, max 2820.1 (n=4)
- Speech-to-text: 0 spoken turns, WER mean None, 0 heard nothing, 0 split into more than one user event
- Checked tokens: 
- Speech usage: 97.8 s streamed to speech-to-text, 1118 characters of bot text (upper bound for text-to-speech); 0 + 0 = 0 USD
- STT price: faster-whisper (local) see integrations.yml, 0.0 USD per minute, from runs on this Mac through CTranslate2 on the CPU; no vendor, no per-use price on 2026-09-30
- TTS price: NeuTTS-2E (local) neutts-2e-Q4_0.gguf on llama.cpp Metal, NeuCodec int8 decoder on ONNX Runtime, 0.0 USD per 1,000 characters, from runs on this Mac; no vendor, no per-use price on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-with-note | normal | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→succeeded/verified_fixture_receipt | 2275, 2176 | 0.114011 |
| recovery-service-unavailable | recovery | pass | verify_patient→verified, select_medication→selected, send_refill_request→awaiting_confirmation, send_refill_request→pending/review_request_not_received, check_request_status→unknown/request_service_unavailable | 3019, 2228 | 0.118541 |

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text and text-to-speech run on this Mac and cost nothing per use.
