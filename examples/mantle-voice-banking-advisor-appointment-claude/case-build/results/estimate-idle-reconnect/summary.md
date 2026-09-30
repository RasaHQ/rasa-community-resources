# banking-advisor-appointment-claude-voice: run summary

- Case: `banking-advisor-appointment`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T05:46:47Z to 2026-09-30T05:48:59Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 1505.3 ms, p95 3471.2 ms, max 3471.2 ms
- LLM calls: 18 (4.5 per caller turn, 3 side-channel, 0 empty completions, 3 failed side-channel calls)
- Tokens: 84539 prompt (0 cached), 1398 completion (of which 193 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 4; reservation_claim: 1; advice_given: 0
- Case metric bookings: 1 over 1 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 3, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 1
- Cost: 0.262045 USD (0.183058 model, 0.078987 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 4 (4 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 1505.3, p95 3471.2, max 3471.2 (n=4)
- End of caller speech to first bot marker, ms: p50 1270.7, p95 3275.9, max 3275.9 (n=4)
- First end marker per turn, ms: rasa_processing p50 956.9, p95 2726.4, max 2726.4 (n=4); tts_first_byte p50 213.7, p95 713.4, max 713.4 (n=4); tts_complete p50 1569.7, p95 4215.2, max 4215.2 (n=4)
- Mantle latency_breakdown (4 turns): user_perceived_latency_ms p50 1170.6, p95 2921.7, max 2921.7 (n=4); llm_generation_before_first_output_ms p50 1139.9, p95 1139.9, max 1139.9 (n=1); first_agent_response.llm_time_to_first_token_ms p50 947.8, p95 1715.3, max 1715.3 (n=4); first_agent_response.llm_total_generation_ms p50 1593.3, p95 2004.6, max 2004.6 (n=4)
- Speech-to-text: 4 spoken turns, WER mean 0.044, 0 heard nothing, 1 split into more than one user event
- Checked tokens: term 2/2 exact, 2/2 after number normalisation; day 2/2 exact, 2/2 after number normalisation; time 1/2 exact, 2/2 after number normalisation; name 0/1 exact, 0/1 after number normalisation
- Speech usage: 119.4 s streamed to speech-to-text, 1321 characters of bot text (upper bound for text-to-speech); 0.012937 + 0.06605 = 0.078987 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime coda, speaker vashti, 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-step-free-branch-at-confirmation | correction | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→declined, release_hold→released, find_advisor_slots→no_capable_slot, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 1505, 454, 3019, 3471 | 0.183058 |

Synthetic scenario: Northgate Bank, its branches, teams, customer and slots are fictional. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; reservation and advice wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is Rime's catalogue label (British), not verified by a listener.
