# banking-advisor-appointment-claude-voice: run summary

- Case: `banking-advisor-appointment`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported n/a)
- Run: 2026-09-30T06:20:47Z to 2026-09-30T06:21:31Z
- Variant `flux-language-en-gb`: language: en-GB in the Flux language_map, so Rasa sends language_hint=en-GB to /v2/listen; a direct probe got HTTP 400 at connect for that parameter
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 0; turn latency p50 None ms, p95 None ms, max None ms
- LLM calls: 0 (None per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 0 prompt (0 cached), 0 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; reservation_claim: 0; advice_given: 0
- Case metric bookings: 0 over 0 tool results
- Case metric callbacks: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 1, deepgram.v2.error 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, northgate.rime_idle_reconnect 0
- Cost: 3e-05 USD (0 model, 3e-05 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 0 (0 spoken); ended by 
- End of caller speech to first bot audio with sound, ms: p50 None, p95 None, max None (n=0)
- End of caller speech to first bot marker, ms: p50 None, p95 None, max None (n=0)
- First end marker per turn, ms: rasa_processing p50 None, p95 None, max None (n=0); tts_first_byte p50 None, p95 None, max None (n=0); tts_complete p50 None, p95 None, max None (n=0)
- Mantle latency_breakdown (0 turns): 
- Speech-to-text: 0 spoken turns, WER mean None, 0 heard nothing, 0 split into more than one user event
- Checked tokens: 
- Speech usage: 0.3 s streamed to speech-to-text, 0 characters of bot text (upper bound for text-to-speech); 3e-05 + 0 = 3e-05 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: rime coda, speaker vashti, 0.05 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter: $0.05 / 1K characters for Coda, $0.03 for Mist) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-remortgage-phone | normal | FAIL | none |  | 0.0 |

## Failed checks

- `normal-remortgage-phone`: {"type": "tool_called", "tool": "book_appointment", "result": {"status": "succeeded", "slot_id": "SLT-MTG-P0814", "purpose": "mortgage", "channel": "phone"}} (0 matching call(s), need >= 1)
- `normal-remortgage-phone`: driver error RuntimeError: no bot turn after caller turn (closed)

Synthetic scenario: Northgate Bank, its branches, teams, customer and slots are fictional. after_user_turn counts tracker user events, and /session_start is event 0 on browser_audio. Checks read the tracker's tool calls and results only, never reply wording; reservation and advice wording in bot text is measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is Rime's catalogue label (British), not verified by a listener.
