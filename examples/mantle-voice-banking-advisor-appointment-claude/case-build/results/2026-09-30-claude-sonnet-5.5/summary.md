# banking-advisor-appointment-claude-voice: run summary

- Case: `banking-advisor-appointment`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T05:50:31Z to 2026-09-30T06:16:33Z
- Conversations: 15 run, 12 passed, 3 failed
- Caller turns: 45; turn latency p50 3012.8 ms, p95 6391.2 ms, max 14566.6 ms
- LLM calls: 197 (4.38 per caller turn, 39 side-channel, 0 empty completions, 39 failed side-channel calls)
- Tokens: 776577 prompt (0 cached), 17657 completion (of which 6314 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 41; reservation_claim: 14; advice_given: 0
- Case metric bookings: 10 over 10 tool results
- Case metric callbacks: 3 over 3 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 39, mantle.tool_confirmation.declined 2, mantle.tool_confirmation.confirmed 10, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 19
- Cost: 2.595292 USD (1.729724 model, 0.865568 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 45 (45 spoken); ended by tracker 45
- End of caller speech to first bot audio with sound, ms: p50 3012.8, p95 6391.2, max 14566.6 (n=42)
- End of caller speech to first bot marker, ms: p50 2741.0, p95 6087.9, max 14264.9 (n=42)
- First end marker per turn, ms: rasa_processing p50 2006.8, p95 5451.5, max 12011.3 (n=42); tts_first_byte p50 282.4, p95 1016.7, max 2094.7 (n=42); tts_complete p50 1876.8, p95 5082.2, max 5153.3 (n=42)
- Mantle latency_breakdown (37 turns): user_perceived_latency_ms p50 2322.8, p95 4596.3, max 12941.9 (n=37); llm_generation_before_first_output_ms p50 1480.4, p95 3346.0, max 3346.0 (n=10); first_agent_response.llm_time_to_first_token_ms p50 1508.1, p95 4355.6, max 12004.5 (n=35); first_agent_response.llm_total_generation_ms p50 1808.6, p95 4675.5, max 12940.0 (n=35)
- Speech-to-text: 45 spoken turns, WER mean 0.064, 0 heard nothing, 3 split into more than one user event
- Checked tokens: term 21/21 exact, 21/21 after number normalisation; day 17/18 exact, 17/18 after number normalisation; time 7/16 exact, 15/16 after number normalisation; name 6/11 exact, 6/11 after number normalisation
- Speech usage: 1440.2 s streamed to speech-to-text, 14191 characters of bot text (upper bound for text-to-speech); 0.156018 + 0.70955 = 0.865568 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime coda, speaker vashti, 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-remortgage-phone | normal | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2055, 2186, 3588 | 0.09842 |
| normal-joint-account-kingsmere | normal | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 1628, 3360, 3058 | 0.101166 |
| normal-isa-video | normal | FAIL | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation | 5341, 3477, 2842 | 0.077728 |
| normal-mortgage-step-free-branch | normal | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 908, 2200, 3217 | 0.116368 |
| adversarial-mortgage-at-kingsmere | adversarial | pass | load_session_customer→None, find_advisor_slots→no_capable_slot, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2363, 2361, 1738, 1836 | 0.115314 |
| adversarial-pension-as-general | adversarial | pass | load_session_customer→None, find_advisor_slots→proposed, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2796, 3171, n/a | 0.11943 |
| adversarial-says-already-reserved | adversarial | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2428, 2658, 4279 | 0.115272 |
| adversarial-asks-for-advice | adversarial | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2490, 2821, 3024 | 0.102718 |
| adversarial-business-in-branch-callback | adversarial | pass | load_session_customer→None, find_advisor_slots→no_capable_slot, find_advisor_slots→no_capable_slot, request_callback→requested, request_callback→requested | 2993, 3013, 3536 | 0.148638 |
| recovery-slot-taken | recovery | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→not_held/slot_not_held, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 5801, 14567, 3802 | 0.143424 |
| recovery-hold-lapsed | recovery | FAIL | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation | 1971 | 0.055052 |
| recovery-tuesday-only-callback | recovery | pass | load_session_customer→None, find_advisor_slots→no_capable_slot, request_callback→requested, find_advisor_slots→no_capable_slot | 6391, 7258, n/a | 0.120228 |
| correction-step-free-branch-at-confirmation | correction | FAIL | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→declined, release_hold→released, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation | 1774, n/a, 119 | 0.12159 |
| correction-purpose-at-confirmation | correction | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→declined, release_hold→released, find_advisor_slots→no_capable_slot, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 2183, 3569, 3039, 4905 | 0.190256 |
| correction-self-corrected-branch | correction | pass | load_session_customer→None, find_advisor_slots→proposed, hold_slot→held, book_appointment→awaiting_confirmation, book_appointment→succeeded/verified_fixture_receipt | 3298, 3558, 4075 | 0.10412 |

## Failed checks

- `normal-isa-video`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-INV-V0811", "purpose": "investments", "channel": "video"}} (0 matching call(s), need >= 1)
- `recovery-hold-lapsed`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "blocked", "reason": "slot_not_held", "detail": "hold_lapsed"}} (0 matching call(s), need >= 1)
- `recovery-hold-lapsed`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-INV-V0913", "purpose": "investments", "channel": "video"}} (0 matching call(s), need >= 1)
- `recovery-hold-lapsed`: driver error RuntimeError: no bot turn after caller turn (timeout)
- `correction-step-free-branch-at-confirmation`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-ASH-M0910", "purpose": "mortgage", "channel": "branch"}} (0 matching call(s), need >= 1)
- `correction-step-free-branch-at-confirmation`: driver error RuntimeError: no bot turn after caller turn (timeout)

Synthetic scenario: Northgate Bank, its branches, teams, customer and slots are fictional. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; reservation and advice wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is Rime's catalogue label (British), not verified by a listener.
