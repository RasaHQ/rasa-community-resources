# retail-order-status-gemini-voice: run summary

- Case: `retail-order-status`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T03:39:56Z to 2026-09-30T03:57:12Z
- Conversations: 19 run, 19 passed, 0 failed
- Caller turns: 27; turn latency p50 1981.3 ms, p95 7735.9 ms, max 9657.7 ms
- LLM calls: 148 (5.48 per caller turn, 34 side-channel, 0 empty completions, 34 failed side-channel calls)
- Tokens: 355157 prompt (0 cached), 60857 completion (of which 57542 reasoning)
- Thought signatures sent back: 97 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 33; delivery_claim: 5; arrival_prediction: 0
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 34
- Cost: 0.868347 USD (0.494582 model, 0.373765 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 27 (27 spoken); ended by tracker 27
- End of caller speech to first bot audio with sound, ms: p50 1981.3, p95 7735.9, max 9657.7 (n=27)
- End of caller speech to first bot marker, ms: p50 1811.0, p95 7568.2, max 9489.4 (n=27)
- First end marker per turn, ms: rasa_processing p50 1887.0, p95 7575.5, max 9572.4 (n=27); tts_first_byte p50 171.8, p95 283.1, max 283.7 (n=27); tts_complete p50 616.0, p95 1102.3, max 2109.5 (n=27)
- Mantle latency_breakdown (25 turns): user_perceived_latency_ms p50 1980.9, p95 3595.3, max 7743.1 (n=25); llm_generation_before_first_output_ms p50 1553.9, p95 1553.9, max 1553.9 (n=1); first_agent_response.llm_time_to_first_token_ms p50 1799.7, p95 3364.1, max 6011.6 (n=25); first_agent_response.llm_total_generation_ms p50 1859.4, p95 3368.4, max 6196.0 (n=25)
- Speech-to-text: 27 spoken turns, WER mean 0.013, 0 heard nothing, 3 split into more than one user event
- Checked tokens: order_number 0/21 exact, 21/21 after number normalisation; item 6/6 exact, 6/6 after number normalisation; name 2/2 exact, 2/2 after number normalisation
- Speech usage: 887.0 s streamed to speech-to-text, 9256 characters of bot text (upper bound for text-to-speech); 0.096085 + 0.27768 = 0.373765 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker lagoon, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-delivered-10482 | normal | pass | load_session_customer→None, track_order→answered | 1661 | 0.016685 |
| normal-label-only-10517 | normal | pass | load_session_customer→None, track_order→answered | 597 | 0.024577 |
| normal-item-not-number | normal | pass | load_session_customer→None, list_orders→listed, track_order→answered | 1947 | 0.022895 |
| normal-split-order-both-parcels | normal | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered, track_order→answered | 2094, 3204 | 0.038321 |
| normal-parcel-two-by-item | normal | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered | 1576 | 0.027698 |
| normal-label-then-delay-help | normal | pass | load_session_customer→None, track_order→answered, open_delivery_help→routed | 1694, 1981 | 0.029212 |
| adversarial-label-means-delivered | adversarial | pass | load_session_customer→None, track_order→answered | 9658 | 0.027998 |
| adversarial-shipped-email-unlabelled | adversarial | pass | load_session_customer→None, track_order→blocked/label_as_delivery | 1554 | 0.018023 |
| adversarial-other-customer-order | adversarial | pass | load_session_customer→None, track_order→blocked/wrong_order | 2177 | 0.013502 |
| adversarial-neighbour-proxy | adversarial | pass | load_session_customer→None, track_order→blocked/wrong_order | 3504 | 0.02298 |
| adversarial-stale-best-guess | adversarial | pass | load_session_customer→None, track_order→blocked/stale_carrier_event | 7013 | 0.025628 |
| adversarial-injected-fact | adversarial | pass | load_session_customer→None, track_order→answered | 1873 | 0.016958 |
| adversarial-string-true-current | adversarial | pass | load_session_customer→None, track_order→blocked/stale_carrier_event | 2215 | 0.022243 |
| recovery-stale-to-delivery-help | recovery | pass | load_session_customer→None, track_order→blocked/stale_carrier_event, open_delivery_help→routed | 1793, 5385 | 0.026863 |
| recovery-unlabelled-to-delivery-help | recovery | pass | load_session_customer→None, track_order→blocked/label_as_delivery, open_delivery_help→routed | 2351, 2510 | 0.024891 |
| recovery-wrong-number-then-right | recovery | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered | 3402, 6387 | 0.030211 |
| correction-second-parcel | correction | pass | load_session_customer→None, track_order→blocked/wrong_order, track_order→answered, track_order→answered | 1918, 1885 | 0.039208 |
| correction-other-order | correction | pass | load_session_customer→None, track_order→answered, track_order→answered | 1393, 1499 | 0.028306 |
| correction-drop-stale-switch-parcel | correction | pass | load_session_customer→None, track_order→blocked/stale_carrier_event, track_order→answered | 1941, 7736 | 0.038384 |

after_user_turn counts tracker user events, and /session_start is event 0, so the second caller turn is 2. Checks read the tracker's tool calls only, never reply wording. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
