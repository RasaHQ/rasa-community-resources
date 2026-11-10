# insurance-roadside-claude-voice: run summary

- Case: `insurance-roadside`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T15:41:21Z to 2026-09-30T15:42:57Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 2101.1 ms, p95 4140.2 ms, max 4140.2 ms
- LLM calls: 14 (3.5 per caller turn, 3 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 52843 prompt (8650 cached, 31200 written to cache), 1829 completion (of which 860 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 2; on_the_way_claim: 0; time_mention: 2
- Case metric dispatches: 1 over 1 tool results
- Case metric dispatched_to_unconfirmed_location: 0 over 1 tool results
- Case metric next_provider_to_unconfirmed_location: 0 over 0 tool results
- Case metric blocked_dispatch_attempts: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.stream_audio.error 0, deepgram_flux.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2, harborcover.turn_order_fix 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.155809 USD (0.124006 model, 0.031803 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 4 (4 spoken); ended by tracker 4
- End of caller speech to first bot audio with sound, ms: p50 2101.1, p95 4140.2, max 4140.2 (n=4)
- End of caller speech to first bot marker, ms: p50 1617.1, p95 3911.6, max 3911.6 (n=4)
- First end marker per turn, ms: rasa_processing p50 1431.0, p95 3687.1, max 3687.1 (n=4); tts_first_byte p50 228.7, p95 574.2, max 574.2 (n=4); tts_complete p50 1320.3, p95 2429.1, max 2429.1 (n=4)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 1936.3, p95 2005.2, max 2005.2 (n=3); llm_generation_before_first_output_ms p50 1145.0, p95 1145.0, max 1145.0 (n=1); first_agent_response.llm_time_to_first_token_ms p50 1294.6, p95 1423.9, max 1423.9 (n=2); first_agent_response.llm_total_generation_ms p50 1643.3, p95 1867.6, max 1867.6 (n=2)
- Speech-to-text: 4 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: policy_number 0/1 exact, 1/1 after number normalisation; name 1/1 exact, 1/1 after number normalisation; exit 0/1 exact, 1/1 after number normalisation
- Speech usage: 83.1 s streamed to speech-to-text, 760 characters of bot text (upper bound for text-to-speech); 0.009003 + 0.0228 = 0.031803 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-use-policy-address | adversarial | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 2101, 2374, 1719, 4140 | 0.124006 |

after_user_turn counts tracker user events, and /session_start is event 0, so the first caller turn is 1. Checks read the tracker's tool calls only, never reply wording; on_the_way_claim and time_mention are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
