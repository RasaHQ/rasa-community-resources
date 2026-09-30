# travel-booking-gpt-voice: run summary

- Case: `travel-booking`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:17:42Z to 2026-09-30T19:19:14Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 4; turn latency p50 1286.8 ms, p95 3813.0 ms, max 3813.0 ms
- LLM calls: 13 (3.25 per caller turn, 3 side-channel, 0 empty completions)
- Tokens: 24201 prompt (7168 cached), 489 completion (of which 40 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 3; all_updated_claim: 0; moved_by_status_claim: 0
- Case metric linked_journey_changes: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.tool.timeout 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, horizon.rime_idle_reconnect 0
- Cost: 0.129061 USD (0.103419 model, 0.025642 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 4 (4 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 1286.8, p95 3813.0, max 3813.0 (n=4)
- End of caller speech to first bot marker, ms: p50 1117.7, p95 3644.9, max 3644.9 (n=4)
- First end marker per turn, ms: rasa_processing p50 870.6, p95 2858.3, max 2858.3 (n=4); tts_first_byte p50 169.3, p95 309.2, max 309.2 (n=4); tts_complete p50 643.1, p95 2624.4, max 2624.4 (n=4)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 1040.2, p95 1327.8, max 1327.8 (n=3); first_agent_response.llm_time_to_first_token_ms p50 761.9, p95 857.8, max 857.8 (n=3); first_agent_response.llm_total_generation_ms p50 3165.0, p95 3354.4, max 3354.4 (n=3)
- Speech-to-text: 4 spoken turns, WER mean 0.011, 0 heard nothing, 0 split into more than one user event
- Checked tokens: booking_reference 0/1 exact, 0/1 after number normalisation
- Speech usage: 67.5 s streamed to speech-to-text, 611 characters of bot text (upper bound for text-to-speech); 0.007312 + 0.01833 = 0.025642 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime mistv3, speaker peak, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-partial-parking-freeze | recovery | FAIL | load_session_traveller→None, find_change_options→not_found, find_change_options→not_found | 2932, 1262, 1287, 3813 | 0.103419 |

## Failed checks

- `recovery-partial-parking-freeze`: {"type": "tool_called", "tool": "apply_journey_change", "result": {"status": "pending", "segment": {"segment": "S3", "after": "HZ 215 2026-10-25T11:15"}, "reason": "partial_journey_change", "service_states": {"PK-1": "unresolved"}}} (0 matching call(s), need >= 1)

Synthetic scenario: Horizon Travel, its partners, traveller, bookings, flights and references are fictional; airport codes and city names are used only as places. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; claims in bot text are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
