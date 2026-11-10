# retail-order-status-gemini-voice: run summary

- Case: `retail-order-status`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T04:01:42Z to 2026-09-30T04:07:47Z
- Variant `thinking-low`: reasoning_effort: low on the orchestrator model (LiteLLM 1.101.2 sends thinkingLevel low), instead of the model's API default
- Conversations: 8 run, 8 passed, 0 failed
- Caller turns: 13; turn latency p50 1347.2 ms, p95 2259.7 ms, max 2259.7 ms
- LLM calls: 67 (5.15 per caller turn, 14 side-channel, 0 empty completions, 14 failed side-channel calls)
- Tokens: 148060 prompt (0 cached), 7638 completion (of which 5915 reasoning)
- Thought signatures sent back: 42 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 13; delivery_claim: 2; arrival_prediction: 0
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 14
- Cost: 0.315488 USD (0.139687 model, 0.175801 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 13 (13 spoken); ended by tracker 13
- End of caller speech to first bot audio with sound, ms: p50 1347.2, p95 2259.7, max 2259.7 (n=13)
- End of caller speech to first bot marker, ms: p50 1180.5, p95 2089.1, max 2089.1 (n=13)
- First end marker per turn, ms: rasa_processing p50 1144.6, p95 2054.5, max 2054.5 (n=13); tts_first_byte p50 171.4, p95 252.8, max 252.8 (n=13); tts_complete p50 584.4, p95 1158.2, max 1158.2 (n=13)
- Mantle latency_breakdown (13 turns): user_perceived_latency_ms p50 1202.0, p95 2225.3, max 2225.3 (n=13); first_agent_response.llm_time_to_first_token_ms p50 1026.5, p95 2048.7, max 2048.7 (n=13); first_agent_response.llm_total_generation_ms p50 1029.3, p95 2143.2, max 2143.2 (n=13)
- Speech-to-text: 13 spoken turns, WER mean 0.022, 0 heard nothing, 2 split into more than one user event
- Checked tokens: item 3/3 exact, 3/3 after number normalisation; order_number 0/8 exact, 8/8 after number normalisation
- Speech usage: 311.6 s streamed to speech-to-text, 4735 characters of bot text (upper bound for text-to-speech); 0.033751 + 0.14205 = 0.175801 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker lagoon, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-item-not-number | normal | pass | load_session_customer→None, list_orders→listed, track_order→answered | 1007 | 0.011005 |
| normal-split-order-both-parcels | normal | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered, track_order→answered | 632, 1133 | 0.017882 |
| normal-label-then-delay-help | normal | pass | load_session_customer→None, track_order→answered, open_delivery_help→routed | 1094, 1742 | 0.022507 |
| adversarial-label-means-delivered | adversarial | pass | load_session_customer→None, track_order→answered | 1347 | 0.011872 |
| adversarial-stale-best-guess | adversarial | pass | load_session_customer→None, track_order→blocked/stale_carrier_event | 112 | 0.011569 |
| recovery-stale-to-delivery-help | recovery | pass | load_session_customer→None, track_order→blocked/stale_carrier_event, open_delivery_help→routed | 1116, 1419 | 0.014408 |
| correction-second-parcel | correction | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered, track_order→answered | 1519, 1400 | 0.027987 |
| correction-drop-stale-switch-parcel | correction | pass | load_session_customer→None, track_order→blocked/stale_carrier_event, track_order→answered | 1591, 2260 | 0.022458 |

after_user_turn counts tracker user events, and /session_start is event 0, so the second caller turn is 2. Checks read the tracker's tool calls only, never reply wording. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
