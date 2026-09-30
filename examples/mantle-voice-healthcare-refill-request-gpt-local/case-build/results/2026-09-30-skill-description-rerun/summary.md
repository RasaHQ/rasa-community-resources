# healthcare-refill-request-gpt-voice-local: run summary

- Case: `healthcare-refill-request`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T01:26:41Z to 2026-09-30T01:27:56Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 4525.7 ms, p95 4969.4 ms, max 4969.4 ms
- LLM calls: 9 (4.5 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 17104 prompt (5632 cached), 406 completion (of which 19 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 1; approval_claim: 0
- Case metric refill_requests_with_effect: 0 over 0 tool results
- Case metric prescription_records_changed: 0 over 1 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, voice_channel.tts_synthesis_error 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, cedar.refill_guard 0, neutts_native.synthesized 5, faster-whisper.transcribed 2
- Cost: 0.072356 USD; model calls priced by LiteLLM 1.101.3 bundled map

## Voice

- Turns: 2 (2 spoken); ended by tracker 2
- End of caller speech to first bot audio with sound, ms: p50 4525.7, p95 4969.4, max 4969.4 (n=2)
- End of caller speech to first bot marker, ms: p50 4338.1, p95 4774.0, max 4774.0 (n=2)
- First end marker per turn, ms: rasa_processing p50 2402.0, p95 2964.6, max 2964.6 (n=2); tts_first_byte p50 187.5, p95 195.3, max 195.3 (n=2); tts_complete p50 616.7, p95 1270.3, max 1270.3 (n=2)
- Mantle latency_breakdown (2 turns): user_perceived_latency_ms p50 2589.5, p95 3159.8, max 3159.8 (n=2); first_agent_response.llm_total_generation_ms p50 2380.0, p95 2956.1, max 2956.1 (n=2)
- Speech-to-text: 2 spoken turns, WER mean 0.019, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 2/2 exact, 2/2 after number normalisation; date 1/2 exact, 2/2 after number normalisation; medication 1/1 exact, 1/1 after number normalisation
- Speech usage: 59.3 s streamed to speech-to-text, 464 characters of bot text (upper bound for text-to-speech); 0 + 0 = 0 USD
- STT price: faster-whisper (local) see integrations.yml, 0.0 USD per minute, from runs on this Mac through CTranslate2 on the CPU; no vendor, no per-use price on 2026-09-30
- TTS price: NeuTTS-2E (local) neutts-2e-Q4_0.gguf on llama.cpp Metal, NeuCodec int8 decoder on ONNX Runtime, 0.0 USD per 1,000 characters, from runs on this Mac; no vendor, no per-use price on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-new-medicine | adversarial | pass | verify_patient→verified, route_clinical_question→routed | 4526, 4969 | 0.072356 |

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text and text-to-speech run on this Mac and cost nothing per use.
