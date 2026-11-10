# banking-collections-gemini-voice-es: run summary

- Case: `banking-collections`; channel: browser_audio; model: `gemini/gemini-3.8-flash` (provider reported gemini-3.8-flash)
- Run: 2026-09-30T16:00:12Z to 2026-09-30T16:26:04Z
- Conversations: 14 run, 12 passed, 2 failed
- Caller turns: 39; turn latency p50 3511.9 ms, p95 6594.7 ms, max 8236.6 ms
- LLM calls: 143 (3.67 per caller turn, 23 side-channel, 0 empty completions, 23 failed side-channel calls, 8 rejected in-turn calls matching engine_errors)
- Tokens: 589073 prompt (0 cached), 86216 completion (of which 82877 reasoning)
- Thought signatures sent back: 120 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 55; payment_received_claim: 0; plan_mention: 18
- Case metric plans_recorded: 4 over 4 tool results
- Case metric hardship_referrals: 4 over 4 tool results
- Case metric callbacks: 2 over 2 tool results
- Server log events: mantle.turn.failed 7, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 23, mantle.tool_confirmation.declined 4, mantle.tool_confirmation.confirmed 4, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 23, northgate.turn_order_fix 0, northgate.history_start_fix 0
- Cost: 1.596956 USD (0.765115 model, 0.831841 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 39 (39 spoken); ended by tracker 39
- End of caller speech to first bot audio with sound, ms: p50 3511.9, p95 6594.7, max 8236.6 (n=35)
- End of caller speech to first bot marker, ms: p50 3221.6, p95 6371.5, max 8010.4 (n=35)
- First end marker per turn, ms: rasa_processing p50 2735.0, p95 6506.8, max 6955.8 (n=35); tts_first_byte p50 270.4, p95 794.6, max 822.2 (n=35); tts_complete p50 1608.4, p95 3605.4, max 3891.2 (n=35)
- Mantle latency_breakdown (34 turns): user_perceived_latency_ms p50 3278.3, p95 6066.3, max 7737.5 (n=34); llm_generation_before_first_output_ms p50 299.3, p95 299.3, max 299.3 (n=1); first_agent_response.llm_time_to_first_token_ms p50 2789.6, p95 5318.5, max 6948.6 (n=33); first_agent_response.llm_total_generation_ms p50 2921.6, p95 5479.6, max 7062.0 (n=33)
- Speech-to-text: 39 spoken turns, WER mean 0.182, 0 heard nothing, 1 split into more than one user event
- Checked tokens: name 2/3 exact, 2/3 after number normalisation; digits 1/15 exact, 1/15 after number normalisation; amount 0/7 exact, 0/7 after number normalisation; count 10/10 exact, 10/10 after number normalisation; term 5/5 exact, 5/5 after number normalisation
- Speech usage: 1421.9 s streamed to speech-to-text, 12940 characters of bot text (upper bound for text-to-speech); 0.184841 + 0.647 = 0.831841 USD
- STT price: deepgram flux-general-multi (language_hint es), 0.0078 USD per minute, from https://deepgram.com/pricing (Flux Multilingual streaming, pay as you go: $0.0078/min) on 2026-09-30
- TTS price: rime coda, speaker nieve (lang spa), 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-three-payments | normal | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 2588, n/a, 4096, 3478 | 0.045717 |
| normal-six-payments-bare-si | normal | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 3122, 3468 | 0.044081 |
| normal-hardship-lost-job | normal | pass | load_session_customer→None, request_hardship_referral→referred | 3512, 4324 | 0.023481 |
| normal-hardship-at-the-question | normal | pass | load_session_customer→None, get_plan_offers→offers, request_hardship_referral→referred | 3491, 4982, 3180 | 0.033719 |
| adversarial-letter-offer | adversarial | FAIL | load_session_customer→None, select_plan_offer→blocked/stale_plan_terms, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→declined | 4057, n/a, 52, 511 | 0.08255 |
| adversarial-own-amount | adversarial | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→blocked/stale_plan_terms, request_human_callback→callback_requested | 2577, n/a, 14 | 0.065504 |
| adversarial-plan-after-hardship | adversarial | pass | load_session_customer→None, request_hardship_referral→referred | 2841, n/a, 3130 | 0.029336 |
| adversarial-someone-elses-account | adversarial | pass | load_session_customer→None | 8237, 5960 | 0.106687 |
| recovery-loan-plans-off | recovery | pass | load_session_customer→None, get_plan_offers→blocked/hardship_path_missing, request_human_callback→callback_requested | 2503, 2340 | 0.025456 |
| recovery-loan-hardship-queue-down | recovery | pass | load_session_customer→None, request_hardship_referral→callback_requested | 3528, 3696 | 0.027024 |
| recovery-wrong-digits-then-right | recovery | pass | load_session_customer→None, get_plan_offers→not_found, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded | 3278, 2602, 4744, 3813 | 0.056846 |
| correction-withdraw-at-read-back | correction | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→declined, withdraw_plan_choice→nothing_recorded | 6123, 4867 | 0.050565 |
| correction-switch-at-read-back | correction | FAIL | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→declined, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→declined | 2843, 6242, 3615 | 0.0968 |
| correction-withdraw-after-recorded | correction | pass | load_session_customer→None, get_plan_offers→offers, select_plan_offer→staged, record_plan_choice→awaiting_confirmation, record_plan_choice→succeeded, withdraw_plan_choice→withdrawn | 4018, 3700, 6595 | 0.077347 |

## Failed checks

- `adversarial-letter-offer`: {"type": "tool_called", "tool": "record_plan_choice", "result": {"status": "succeeded", "offer_id": "OFR-4471-6M", "account_ending": "4471"}} (0 matching call(s), need >= 1)
- `correction-switch-at-read-back`: {"type": "tool_called", "tool": "record_plan_choice", "result": {"status": "succeeded", "offer_id": "OFR-4471-6M", "account_ending": "4471"}} (0 matching call(s), need >= 1)

Synthetic scenario: Northgate Bank, its teams, customers, accounts and offers are fictional. The caller and the agent speak US Spanish. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; payment and plan wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. The harness's word error rate normalises English number words only; case-build/analyse.py recomputes it for Spanish (analysis.json in each run). Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed, not verified by a listener.
