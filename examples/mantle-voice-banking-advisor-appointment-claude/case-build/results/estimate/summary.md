# banking-advisor-appointment-claude-voice: run summary

- Case: `banking-advisor-appointment`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T05:37:06Z to 2026-09-30T05:39:30Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 2; turn latency p50 1045.7 ms, p95 2087.6 ms, max 2087.6 ms
- LLM calls: 9 (4.5 per caller turn, 1 side-channel, 0 empty completions, 1 failed side-channel calls)
- Tokens: 40753 prompt (0 cached), 1016 completion (of which 296 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 2; reservation_claim: 0; advice_given: 0
- Case metric bookings: 0 over 0 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 1, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 1, voice_channel.agent_task_failed 1
- Cost: 0.136773 USD (0.091666 model, 0.045107 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 2 (2 spoken); ended by tracker 2
- End of caller speech to first bot audio with sound, ms: p50 1045.7, p95 2087.6, max 2087.6 (n=2)
- End of caller speech to first bot marker, ms: p50 833.0, p95 1872.7, max 1872.7 (n=2)
- First end marker per turn, ms: rasa_processing p50 484.1, p95 1202.8, max 1202.8 (n=2); tts_first_byte p50 212.5, p95 215.1, max 215.1 (n=2); tts_complete p50 487.5, p95 1469.6, max 1469.6 (n=2)
- Mantle latency_breakdown (2 turns): user_perceived_latency_ms p50 1417.7, p95 1810.6, max 1810.6 (n=2); first_agent_response.llm_time_to_first_token_ms p50 870.9, p95 1590.7, max 1590.7 (n=2); first_agent_response.llm_total_generation_ms p50 1228.9, p95 2561.7, max 2561.7 (n=2)
- Speech-to-text: 2 spoken turns, WER mean 0.026, 0 heard nothing, 1 split into more than one user event
- Checked tokens: term 2/2 exact, 2/2 after number normalisation; day 1/1 exact, 1/1 after number normalisation; time 1/1 exact, 1/1 after number normalisation
- Speech usage: 75.8 s streamed to speech-to-text, 738 characters of bot text (upper bound for text-to-speech); 0.008207 + 0.0369 = 0.045107 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime coda, speaker vashti, 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-step-free-branch-at-confirmation | correction | FAIL | load_session_customer→None, find_advisor_slots→proposed, find_advisor_slots→no_capable_slot | 2088, 1046 | 0.091666 |

## Failed checks

- `correction-step-free-branch-at-confirmation`: {"type": "tool_called", "tool": "release_hold", "result": {"status": "released", "slot_id": "SLT-MTG-P0814"}} (0 matching call(s), need >= 1)
- `correction-step-free-branch-at-confirmation`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-ASH-M0910", "purpose": "mortgage", "channel": "branch"}} (0 matching call(s), need >= 1)
- `correction-step-free-branch-at-confirmation`: driver error RuntimeError: no bot turn after caller turn (closed)

Synthetic scenario: Northgate Bank, its branches, teams, customer and slots are fictional. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; reservation and advice wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is Rime's catalogue label (British), not verified by a listener.
