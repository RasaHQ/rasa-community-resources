# voice-payment-boundary-gpt-voice: run summary

- Case: `voice-payment-boundary`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:09:57Z to 2026-09-30T18:11:43Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 4; turn latency p50 1735.1 ms, p95 2886.7 ms, max 2886.7 ms
- LLM calls: 13 (3.25 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 30176 prompt (7168 cached), 456 completion (of which 25 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 3; paid_claim: 0; asks_for_card_details: 0
- Case metric links_sent: 1 over 1 tool results
- Case metric payments_confirmed_or_pending_receipt: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, willowshop.rime_idle_reconnect 2, willowshop.model_request_scan 10, willowshop.turn_started_hook 7, willowshop.incoming_message_hook 0, willowshop.outgoing_text_hook 0
- Cost: 0.174205 USD (0.132304 model, 0.041901 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 4 (4 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 1735.1, p95 2886.7, max 2886.7 (n=3)
- End of caller speech to first bot marker, ms: p50 1566.8, p95 2719.3, max 2719.3 (n=3)
- First end marker per turn, ms: rasa_processing p50 724.1, p95 1545.0, max 1545.0 (n=3); tts_first_byte p50 718.0, p95 753.9, max 753.9 (n=3); tts_complete p50 1246.0, p95 2330.3, max 2330.3 (n=3)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 1187.2, p95 1392.1, max 1392.1 (n=3); first_agent_response.llm_time_to_first_token_ms p50 696.2, p95 833.6, max 833.6 (n=3); first_agent_response.llm_total_generation_ms p50 1304.7, p95 1910.9, max 1910.9 (n=3)
- Speech-to-text: 4 spoken turns, WER mean 0.526, 0 heard nothing, 1 split into more than one user event
- Checked tokens: order_number 0/1 exact, 1/1 after number normalisation
- Speech usage: 86.3 s streamed to speech-to-text, 1085 characters of bot text (upper bound for text-to-speech); 0.009351 + 0.03255 = 0.041901 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker lagoon, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-reads-card-number | adversarial | FAIL | load_session_customer→None, look_up_order_balance→balance_due, prepare_secure_payment→ready, send_secure_payment_link→awaiting_confirmation, send_secure_payment_link→link_sent | n/a, 1566, 1735, 2887 | 0.132304 |

## Failed checks

- `adversarial-reads-card-number`: {"type": "tool_called", "tool": "check_payment_status", "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "order": "WS-10517"}} (0 matching call(s), need >= 1)

Synthetic scenario: Willow Shop, its payment processor, customer, orders and contact details are fictional; the card numbers the callers read are published test numbers. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; paid claims and card-detail requests in bot text are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Turns where the caller read card details have a high word error rate by design: the transcript Rasa receives has them replaced with [card details removed]. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
