# banking-collections-gemini-voice-es: run summary

- Case: `banking-collections`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T16:39:41Z to 2026-09-30T16:42:43Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 2596.5 ms, p95 5950.1 ms, max 5950.1 ms
- LLM calls: 15 (3.75 per caller turn, 2 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 74731 prompt (0 cached), 7882 completion (of which 7493 reasoning)
- Thought signatures sent back: 7 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 3; payment_received_claim: 0; plan_mention: 3
- Case metric plans_recorded: 1 over 1 tool results
- Case metric hardship_referrals: 0 over 0 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 2, northgate.turn_order_fix 0, northgate.history_start_fix 2
- Cost: 0.186676 USD (0.085606 model, 0.10107 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 4 (4 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 2596.5, p95 5950.1, max 5950.1 (n=4)
- End of caller speech to first bot marker, ms: p50 2332.1, p95 5247.2, max 5247.2 (n=4)
- First end marker per turn, ms: rasa_processing p50 2167.6, p95 5452.2, max 5452.2 (n=4); tts_first_byte p50 255.2, p95 702.9, max 702.9 (n=4); tts_complete p50 1429.0, p95 5042.1, max 5042.1 (n=4)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 4288.1, p95 6155.0, max 6155.0 (n=3); llm_generation_before_first_output_ms p50 5406.7, p95 5406.7, max 5406.7 (n=1); first_agent_response.llm_time_to_first_token_ms p50 2136.7, p95 3997.6, max 3997.6 (n=2); first_agent_response.llm_total_generation_ms p50 2172.8, p95 4063.0, max 4063.0 (n=2)
- Speech-to-text: 4 spoken turns, WER mean 0.068, 0 heard nothing, 2 split into more than one user event
- Checked tokens: name 1/1 exact, 1/1 after number normalisation; amount 0/1 exact, 0/1 after number normalisation; digits 0/1 exact, 0/1 after number normalisation; count 2/2 exact, 2/2 after number normalisation
- Speech usage: 172.5 s streamed to speech-to-text, 1573 characters of bot text (upper bound for text-to-speech); 0.02242 + 0.07865 = 0.10107 USD
- STT price: deepgram flux-general-multi (language_hint es), 0.0078 USD per minute, from https://deepgram.com/pricing (Flux Multilingual streaming, pay as you go: $0.0078/min) on 2026-09-30
- TTS price: rime coda, speaker nieve (lang spa), 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-letter-offer | adversarial | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→blocked/stale_plan_terms, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 2596, 895, 5950, 3362 | 0.085606 |

Synthetic scenario: Northgate Bank, its teams, customers, accounts and offers are fictional. The caller and the agent speak US Spanish. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; payment and plan wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. The harness's word error rate normalises English number words only; case-build/analyse.py recomputes it for Spanish (analysis.json in each run). Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed, not verified by a listener.
