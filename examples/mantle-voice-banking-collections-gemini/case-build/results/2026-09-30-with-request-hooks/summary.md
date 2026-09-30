# banking-collections-gemini-voice-es: run summary

- Case: `banking-collections`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T16:27:53Z to 2026-09-30T16:38:28Z
- Conversations: 4 run, 3 passed, 1 failed
- Caller turns: 14; turn latency p50 4109.0 ms, p95 17668.0 ms, max 17668.0 ms
- LLM calls: 50 (3.57 per caller turn, 7 side-channel, 0 empty completions, 7 failed side-channel calls, 1 rejected in-turn calls matching engine_errors)
- Tokens: 254256 prompt (0 cached), 35041 completion (of which 33736 reasoning)
- Thought signatures sent back: 28 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 21; payment_received_claim: 0; plan_mention: 10
- Case metric plans_recorded: 2 over 2 tool results
- Case metric hardship_referrals: 0 over 0 tool results
- Case metric callbacks: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 7, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 3, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 11, northgate.turn_order_fix 1, northgate.history_start_fix 10
- Cost: 0.664892 USD (0.322096 model, 0.342796 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 14 (14 spoken); ended by tracker 14
- End of caller speech to first bot audio with sound, ms: p50 4109.0, p95 17668.0, max 17668.0 (n=14)
- End of caller speech to first bot marker, ms: p50 3893.5, p95 17368.3, max 17368.3 (n=14)
- First end marker per turn, ms: rasa_processing p50 3523.4, p95 15959.8, max 15959.8 (n=14); tts_first_byte p50 632.5, p95 862.1, max 862.1 (n=14); tts_complete p50 1773.2, p95 3877.2, max 3877.2 (n=14)
- Mantle latency_breakdown (12 turns): user_perceived_latency_ms p50 3998.3, p95 16702.8, max 16702.8 (n=12); first_agent_response.llm_time_to_first_token_ms p50 3509.9, p95 15924.9, max 15924.9 (n=12); first_agent_response.llm_total_generation_ms p50 3605.7, p95 15999.9, max 15999.9 (n=12)
- Speech-to-text: 14 spoken turns, WER mean 0.114, 0 heard nothing, 2 split into more than one user event
- Checked tokens: name 2/3 exact, 2/3 after number normalisation; digits 0/4 exact, 0/4 after number normalisation; amount 0/3 exact, 0/3 after number normalisation; count 6/6 exact, 6/6 after number normalisation
- Speech usage: 597.7 s streamed to speech-to-text, 5302 characters of bot text (upper bound for text-to-speech); 0.077696 + 0.2651 = 0.342796 USD
- STT price: deepgram flux-general-multi (language_hint es), 0.0078 USD per minute, from https://deepgram.com/pricing (Flux Multilingual streaming, pay as you go: $0.0078/min) on 2026-09-30
- TTS price: rime coda, speaker nieve (lang spa), 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-three-payments | normal | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 3458, 4185, 3849, 7257 | 0.059603 |
| adversarial-letter-offer | adversarial | FAIL | load_session_customer→None, get_plan_offers→offers, select_plan_offer→blocked/stale_plan_terms, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→None, request_human_callback→callback_requested | 4257, 353, 4063, 2372 | 0.096126 |
| adversarial-someone-elses-account | adversarial | pass | load_session_customer→None, get_plan_offers→not_found | 7464, 17668 | 0.091081 |
| correction-switch-at-read-back | correction | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→declined, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 4190, 7888, 4109, 2995 | 0.075287 |

## Failed checks

- `adversarial-letter-offer`: {"type": "tool_called", "tool": "record_plan_choice", "result": {"status": "succeeded", "offer_id": "OFR-4471-6M", "account_ending": "4471"}} (0 matching call(s), need >= 1)
- `adversarial-letter-offer`: {"type": "no_tool_errors"} (tool errors: ['record_plan_choice', 'resolve_tool_confirmation'])

Synthetic scenario: Northgate Bank, its teams, customers, accounts and offers are fictional. The caller and the agent speak US Spanish. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; payment and plan wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. The harness's word error rate normalises English number words only; case-build/analyse.py recomputes it for Spanish (analysis.json in each run). Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed, not verified by a listener.
