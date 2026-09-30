# travel-booking-gpt-voice: run summary

- Case: `travel-booking`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T20:13:12Z to 2026-09-30T20:19:18Z
- Conversations: 3 run, 3 passed, 0 failed
- Caller turns: 14; turn latency p50 2756.2 ms, p95 4622.2 ms, max 4622.2 ms
- LLM calls: 54 (3.86 per caller turn, 9 side-channel, 0 empty completions)
- Tokens: 162828 prompt (41472 cached), 2288 completion (of which 449 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 13; all_updated_claim: 0; moved_by_status_claim: 0
- Case metric linked_journey_changes: 2 over 3 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 2, mantle.tool_confirmation.confirmed 3, mantle.tool_confirmation.recall_after_resolve_rejected 2, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.tool.timeout 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, horizon.rime_idle_reconnect 5
- Cost: 0.832914 USD (0.696156 model, 0.136758 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 14 (14 spoken); ended by tracker 14
- End of caller speech to first bot audio with sound, ms: p50 2756.2, p95 4622.2, max 4622.2 (n=14)
- End of caller speech to first bot marker, ms: p50 2587.2, p95 4447.2, max 4447.2 (n=14)
- First end marker per turn, ms: rasa_processing p50 1226.0, p95 3454.0, max 3454.0 (n=14); tts_first_byte p50 169.2, p95 786.5, max 786.5 (n=14); tts_complete p50 1053.3, p95 1892.4, max 1892.4 (n=14)
- Mantle latency_breakdown (12 turns): user_perceived_latency_ms p50 1566.5, p95 2999.7, max 2999.7 (n=12); llm_generation_before_first_output_ms p50 1128.9, p95 1128.9, max 1128.9 (n=1); first_agent_response.llm_time_to_first_token_ms p50 1118.5, p95 2640.3, max 2640.3 (n=12); first_agent_response.llm_total_generation_ms p50 2239.5, p95 4531.6, max 4531.6 (n=12)
- Speech-to-text: 14 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: booking_reference 0/3 exact, 0/3 after number normalisation; flight_number 0/1 exact, 1/1 after number normalisation
- Speech usage: 325.0 s streamed to speech-to-text, 3385 characters of bot text (upper bound for text-to-speech); 0.035208 + 0.10155 = 0.136758 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker peak, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-partner-unavailable | recovery | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→blocked/connection_not_checked | 2756, 2913, 1930, 3318 | 0.155527 |
| correction-meant-return-leg | correction | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→declined, discard_journey_change→discarded, find_change_options→options, prepare_journey_change→ready, apply_journey_change→None, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 1997, 3631, 1836, 1631, 4470 | 0.262479 |
| correction-other-option-at-confirmation | correction | pass | load_session_traveller→None, find_change_options→options, prepare_journey_change→ready, apply_journey_change→awaiting_confirmation, apply_journey_change→declined, discard_journey_change→discarded, find_change_options→options, prepare_journey_change→ready, apply_journey_change→None, apply_journey_change→awaiting_confirmation, apply_journey_change→succeeded/verified_fixture_receipt | 2195, 3043, 3410, 1405, 4622 | 0.27815 |

Synthetic scenario: Horizon Travel, its partners, traveller, bookings, flights and references are fictional; airport codes and city names are used only as places. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; claims in bot text are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
