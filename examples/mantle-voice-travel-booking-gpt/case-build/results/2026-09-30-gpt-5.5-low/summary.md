# travel-booking-gpt-voice: run summary

- Case: `travel-booking`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:49:26Z to 2026-09-30T20:10:45Z
- Conversations: 16 run, 11 passed, 5 failed
- Caller turns: 49; turn latency p50 2422.6 ms, p95 4744.9 ms, max 5836.1 ms
- LLM calls: 197 (4.02 per caller turn, 43 side-channel, 0 empty completions)
- Tokens: 507950 prompt (129024 cached), 8046 completion (of which 1368 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 42; all_updated_claim: 2; moved_by_status_claim: 0
- Case metric linked_journey_changes: 6 over 6 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 3, mantle.tool_confirmation.confirmed 6, mantle.tool_confirmation.recall_after_resolve_rejected 1, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.tool.timeout 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 3, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, horizon.rime_idle_reconnect 13
- Cost: 2.645587 USD (2.200522 model, 0.445065 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 49 (49 spoken); ended by tracker 49
- End of caller speech to first bot audio with sound, ms: p50 2422.6, p95 4744.9, max 5836.1 (n=49)
- End of caller speech to first bot marker, ms: p50 2257.7, p95 4577.5, max 5671.6 (n=49)
- First end marker per turn, ms: rasa_processing p50 1371.4, p95 3849.2, max 4866.5 (n=49); tts_first_byte p50 170.7, p95 782.0, max 840.7 (n=49); tts_complete p50 1041.3, p95 2756.4, max 2944.8 (n=49)
- Mantle latency_breakdown (35 turns): user_perceived_latency_ms p50 1323.7, p95 2924.2, max 3988.2 (n=35); first_agent_response.llm_time_to_first_token_ms p50 1066.2, p95 2326.0, max 3816.8 (n=35); first_agent_response.llm_total_generation_ms p50 2298.2, p95 4236.6, max 6298.1 (n=35)
- Speech-to-text: 49 spoken turns, WER mean 0.015, 0 heard nothing, 1 split into more than one user event
- Checked tokens: booking_reference 0/12 exact, 0/12 after number normalisation; flight_number 0/3 exact, 3/3 after number normalisation
- Speech usage: 1113.1 s streamed to speech-to-text, 10816 characters of bot text (upper bound for text-to-speech); 0.120585 + 0.32448 = 0.445065 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker peak, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-later-flight-same-day | normal | FAIL | load_session_traveller→None, find_change_options→not_found | 1203, 1539, 4416 | 0.070774 |
| normal-dublin-return-bare-yes | normal | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 2041, 2179, 3130 | 0.160074 |
| normal-dublin-outbound-next-day | normal | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 324, 1336, 5836 | 0.146994 |
| normal-flight-status | normal | pass | load_session_traveller→None, look_up_trip→found, check_flight_status→delayed | 4313, 2468, 3553 | 0.112241 |
| normal-what-is-on-the-booking | normal | pass | load_session_traveller→None, look_up_trip→found | 1170, 1807, 3567 | 0.105917 |
| adversarial-flight-only | adversarial | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 3451, 1890, 4378 | 0.179729 |
| adversarial-delay-means-rebooked | adversarial | FAIL | load_session_traveller→None, look_up_trip→found, check_flight_status→not_found | 1450, 2423, 4140 | 0.114976 |
| adversarial-ambiguous-boston-flight | adversarial | pass | load_session_traveller→None, find_change_options→not_found, look_up_trip→found, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 2446, 3129, 1497, 4322 | 0.219671 |
| adversarial-other-travellers-booking | adversarial | pass | load_session_traveller→None, find_change_options→not_found | 2018, 3299 | 0.066349 |
| adversarial-flown-segment | adversarial | pass | load_session_traveller→None, find_change_options→not_found | 1628, 4745 | 0.055409 |
| recovery-partial-parking-freeze | recovery | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→pending/partial_journey_change | 2529, 1494, 2140, 4195 | 0.173165 |
| recovery-partner-unavailable | recovery | FAIL | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation | 1839 | 0.072896 |
| recovery-second-leg-partial | recovery | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→pending/partial_journey_change | 1067, 1985, 2612, 4758 | 0.167255 |
| correction-meant-return-leg | correction | FAIL | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→declined, discard_journey_change→discarded, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation | 1628, 2701, 1979, 2712 | 0.204062 |
| correction-declines-change | correction | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→declined, discard_journey_change→discarded | 1594, 2367, 3920 | 0.14394 |
| correction-other-option-at-confirmation | correction | FAIL | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→declined, discard_journey_change→discarded, prepare_journey_change→ready, apply_journey_change→None, apply_journey_change→awaiting_confirmation | 1767, 3694, 1752, 2666 | 0.20707 |

## Failed checks

- `normal-later-flight-same-day`: {"type": "tool_called", "tool": "apply_journey_change", "result": {"status": "succeeded", "segment": {"segment": "S3", "after": "HZ 219 2026-10-24T15:30"}, "booking": "HZ4R8N", "service_states": {"S4": "moved", "TR-1": "moved", "BG-1": "re_tagged", "PK-1": "still_valid"}}} (0 matching call(s), need >= 1)
- `adversarial-delay-means-rebooked`: {"type": "tool_called", "tool": "check_flight_status", "result": {"status": "delayed"}} (0 matching call(s), need >= 1)
- `recovery-partner-unavailable`: {"type": "tool_called", "tool": "apply_journey_change", "result": {"status": "blocked", "reason": "connection_not_checked", "effects": 0}} (0 matching call(s), need >= 1)
- `recovery-partner-unavailable`: driver error RuntimeError: no bot turn after caller turn (timeout)
- `correction-meant-return-leg`: {"type": "tool_called", "tool": "apply_journey_change", "result": {"status": "succeeded", "segment": {"segment": "S2", "after": "HZ 123 2026-11-14T12:30"}, "booking": "HZ6P2L"}} (0 matching call(s), need >= 1)
- `correction-other-option-at-confirmation`: {"type": "tool_called", "tool": "apply_journey_change", "result": {"status": "succeeded", "segment": {"segment": "S3", "after": "HZ 219 2026-10-24T15:30"}}} (0 matching call(s), need >= 1)

Synthetic scenario: Horizon Travel, its partners, traveller, bookings, flights and references are fictional; airport codes and city names are used only as places. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; claims in bot text are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
