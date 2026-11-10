# retail-order-status-gemini-voice: run summary

- Case: `retail-order-status`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported n/a)
- Run: 2026-09-30T04:00:27Z to 2026-09-30T04:01:11Z
- Variant `thinking-minimal`: reasoning_effort: minimal on the orchestrator model (LiteLLM maps it to Gemini's lowest thinking level), instead of the model's API default
- Conversations: 2 run, 0 passed, 0 failed, 2 lost to provider errors, 6 skipped for budget
- Caller turns: 3; turn latency p50 74.6 ms, p95 498.2 ms, max 498.2 ms
- LLM calls: 5 (1.67 per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 0 prompt (0 cached), 0 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; delivery_claim: 0; arrival_prediction: 0
- Server log events: mantle.turn.failed 5, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.015924 USD (0 model, 0.015924 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 3 (3 spoken); ended by tracker 3
- End of caller speech to first bot audio with sound, ms: p50 74.6, p95 498.2, max 498.2 (n=2)
- End of caller speech to first bot marker, ms: p50 74.5, p95 276.2, max 276.2 (n=2)
- First end marker per turn, ms: rasa_processing p50 200.1, p95 296.9, max 296.9 (n=2); tts_first_byte p50 0.2, p95 222.1, max 222.1 (n=2); tts_complete p50 1.8, p95 876.5, max 876.5 (n=2)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 231.5, p95 518.9, max 518.9 (n=3); llm_generation_before_first_output_ms p50 207.1, p95 246.8, max 246.8 (n=3)
- Speech-to-text: 3 spoken turns, WER mean 0.067, 0 heard nothing, 0 split into more than one user event
- Checked tokens: item 1/1 exact, 1/1 after number normalisation; order_number 0/1 exact, 1/1 after number normalisation
- Speech usage: 29.0 s streamed to speech-to-text, 426 characters of bot text (upper bound for text-to-speech); 0.003144 + 0.01278 = 0.015924 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker lagoon, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-item-not-number | normal | ERROR (provider) | load_session_customer→None | 498 | 0 |
| normal-split-order-both-parcels | normal | ERROR (provider) | load_session_customer→None | n/a, 75 | 0 |

## Provider errors

- `normal-item-not-number`: 2 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `normal-split-order-both-parcels`: 3 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

after_user_turn counts tracker user events, and /session_start is event 0, so the second caller turn is 2. Checks read the tracker's tool calls only, never reply wording. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
