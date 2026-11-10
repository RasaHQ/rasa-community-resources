# banking-advisor-appointment-claude-voice: run summary

- Case: `banking-advisor-appointment`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T06:21:48Z to 2026-09-30T06:28:00Z
- Conversations: 3 run, 2 passed, 1 failed
- Caller turns: 10; turn latency p50 3459.7 ms, p95 30328.9 ms, max 30328.9 ms
- LLM calls: 41 (4.1 per caller turn, 8 side-channel, 0 empty completions, 8 failed side-channel calls, 2 rejected in-turn calls matching engine_errors)
- Tokens: 154278 prompt (0 cached), 2749 completion (of which 691 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 6; reservation_claim: 2; advice_given: 0
- Case metric bookings: 2 over 2 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 1, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 8, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 5
- Cost: 0.491802 USD (0.336046 model, 0.155756 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 10 (10 spoken); ended by tracker 10
- End of caller speech to first bot audio with sound, ms: p50 3459.7, p95 30328.9, max 30328.9 (n=9)
- End of caller speech to first bot marker, ms: p50 3232.4, p95 29696.5, max 29696.5 (n=9)
- First end marker per turn, ms: rasa_processing p50 2524.0, p95 5985.8, max 5985.8 (n=9); tts_first_byte p50 217.5, p95 798.8, max 798.8 (n=9); tts_complete p50 1642.1, p95 4990.5, max 4990.5 (n=9)
- Mantle latency_breakdown (9 turns): user_perceived_latency_ms p50 2751.4, p95 4772.0, max 4772.0 (n=9); llm_generation_before_first_output_ms p50 1172.1, p95 3013.0, max 3013.0 (n=4); first_agent_response.llm_time_to_first_token_ms p50 1897.6, p95 4575.5, max 4575.5 (n=7); first_agent_response.llm_total_generation_ms p50 2178.1, p95 4966.0, max 4966.0 (n=7)
- Speech-to-text: 10 spoken turns, WER mean 0.169, 1 heard nothing, 0 split into more than one user event
- Checked tokens: term 4/5 exact, 4/5 after number normalisation; day 3/4 exact, 3/4 after number normalisation; time 2/4 exact, 4/4 after number normalisation; name 0/1 exact, 0/1 after number normalisation
- Speech usage: 343.4 s streamed to speech-to-text, 2371 characters of bot text (upper bound for text-to-speech); 0.037206 + 0.11855 = 0.155756 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime coda, speaker vashti, 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-isa-video | normal | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2206, 3460, 4771 | 0.097166 |
| recovery-hold-lapsed | recovery | FAIL | load_session_customer→None, find_advisor_slots→blocked/wrong_advisor_capability | 2542, 30329, 1947 | 0.055364 |
| correction-step-free-branch-at-confirmation | correction | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→declined, release_hold→released, find_advisor_slots→no_capable_slot, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 5236, n/a, 16, 4234 | 0.183516 |

## Failed checks

- `recovery-hold-lapsed`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "blocked", "reason": "slot_not_held", "detail": "hold_lapsed"}} (0 matching call(s), need >= 1)
- `recovery-hold-lapsed`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-INV-V0913", "purpose": "investments", "channel": "video"}} (0 matching call(s), need >= 1)
- `recovery-hold-lapsed`: driver error RuntimeError: no bot turn after caller turn (timeout)

Synthetic scenario: Northgate Bank, its branches, teams, customer and slots are fictional. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; reservation and advice wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is Rime's catalogue label (British), not verified by a listener.
