# banking-collections-gemini-voice-es: run summary

- Case: `banking-collections`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T16:44:22Z to 2026-09-30T16:50:35Z
- Conversations: 3 run, 3 passed, 0 failed
- Caller turns: 9; turn latency p50 2958.7 ms, p95 5994.5 ms, max 5994.5 ms
- LLM calls: 32 (3.56 per caller turn, 6 side-channel, 0 empty completions, 6 failed side-channel calls, 1 rejected in-turn calls matching engine_errors)
- Tokens: 110926 prompt (0 cached), 12086 completion (of which 11367 reasoning)
- Thought signatures sent back: 24 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 14; payment_received_claim: 0; plan_mention: 6
- Case metric plans_recorded: 2 over 2 tool results
- Case metric hardship_referrals: 1 over 1 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 6, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 4, northgate.turn_order_fix 0, northgate.history_start_fix 6
- Cost: 0.334573 USD (0.128517 model, 0.206056 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 9 (9 spoken); ended by tracker 9
- End of caller speech to first bot audio with sound, ms: p50 2958.7, p95 5994.5, max 5994.5 (n=9)
- End of caller speech to first bot marker, ms: p50 2714.5, p95 5781.6, max 5781.6 (n=9)
- First end marker per turn, ms: rasa_processing p50 2205.6, p95 5254.6, max 5254.6 (n=9); tts_first_byte p50 299.2, p95 833.8, max 833.8 (n=9); tts_complete p50 1756.9, p95 3823.4, max 3823.4 (n=9)
- Mantle latency_breakdown (8 turns): user_perceived_latency_ms p50 2579.0, p95 5884.5, max 5884.5 (n=8); first_agent_response.llm_time_to_first_token_ms p50 2179.2, p95 5233.4, max 5233.4 (n=8); first_agent_response.llm_total_generation_ms p50 2287.3, p95 5294.0, max 5294.0 (n=8)
- Speech-to-text: 9 spoken turns, WER mean 0.144, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 1/1 exact, 1/1 after number normalisation; digits 0/3 exact, 0/3 after number normalisation; amount 0/1 exact, 0/1 after number normalisation; count 2/2 exact, 2/2 after number normalisation; term 2/2 exact, 2/2 after number normalisation
- Speech usage: 345.0 s streamed to speech-to-text, 3224 characters of bot text (upper bound for text-to-speech); 0.044856 + 0.1612 = 0.206056 USD
- STT price: deepgram flux-general-multi (language_hint es), 0.0078 USD per minute, from https://deepgram.com/pricing (Flux Multilingual streaming, pay as you go: $0.0078/min) on 2026-09-30
- TTS price: rime coda, speaker nieve (lang spa), 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-three-payments | normal | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 2058, 2247, 3338, 2959 | 0.046609 |
| normal-hardship-lost-job | normal | pass | load_session_customer→None, request_hardship_referral→referred | 2565, 2672 | 0.023069 |
| correction-withdraw-after-recorded | correction | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded, withdraw_plan_choice→withdrawn | 3939, 5994, 4598 | 0.058838 |

Synthetic scenario: Northgate Bank, its teams, customers, accounts and offers are fictional. The caller and the agent speak US Spanish. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; payment and plan wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. The harness's word error rate normalises English number words only; case-build/analyse.py recomputes it for Spanish (analysis.json in each run). Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed, not verified by a listener.
