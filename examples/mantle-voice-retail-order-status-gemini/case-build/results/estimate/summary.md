# retail-order-status-gemini-voice: run summary

- Case: `retail-order-status`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T03:36:40Z to 2026-09-30T03:39:23Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 2479.0 ms, p95 9822.5 ms, max 9822.5 ms
- LLM calls: 10 (5.0 per caller turn, 2 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 30075 prompt (0 cached), 4385 completion (of which 4115 reasoning)
- Thought signatures sent back: 7 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 1; delivery_claim: 1; arrival_prediction: 0
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2
- Cost: 0.065938 USD (0.039 model, 0.026938 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 2 (2 spoken); ended by tracker 2
- End of caller speech to first bot audio with sound, ms: p50 2479.0, p95 9822.5, max 9822.5 (n=2)
- End of caller speech to first bot marker, ms: p50 2312.4, p95 9655.3, max 9655.3 (n=2)
- First end marker per turn, ms: rasa_processing p50 2714.8, p95 9660.7, max 9660.7 (n=2); tts_first_byte p50 166.7, p95 167.3, max 167.3 (n=2); tts_complete p50 580.0, p95 1313.5, max 1313.5 (n=2)
- Mantle latency_breakdown (2 turns): user_perceived_latency_ms p50 2881.5, p95 9827.9, max 9827.9 (n=2); llm_generation_before_first_output_ms p50 2737.2, p95 2737.2, max 2737.2 (n=1); first_agent_response.llm_time_to_first_token_ms p50 2289.7, p95 6907.0, max 6907.0 (n=2); first_agent_response.llm_total_generation_ms p50 2299.8, p95 7138.4, max 7138.4 (n=2)
- Speech-to-text: 2 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: order_number 0/1 exact, 1/1 after number normalisation
- Speech usage: 73.6 s streamed to speech-to-text, 632 characters of bot text (upper bound for text-to-speech); 0.007978 + 0.01896 = 0.026938 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker lagoon, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-split-order-both-parcels | normal | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered, track_order→answered | 2479, 9822 | 0.039 |

after_user_turn counts tracker user events, and /session_start is event 0, so the second caller turn is 2. Checks read the tracker's tool calls only, never reply wording. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
