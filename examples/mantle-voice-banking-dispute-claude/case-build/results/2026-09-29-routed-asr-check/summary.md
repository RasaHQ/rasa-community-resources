# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported n/a)
- Run: 2026-09-29T23:04:40Z to 2026-09-29T23:05:25Z
- Variant `routed-asr`: The same Speechmatics engine wrapped in voicerouter.RoutedASR (one provider), to check live whether Rasa's ASR keep-alive task, which reads asr_engine.config, breaks the call on the router
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 0; turn latency p50 None ms, p95 None ms, max None ms
- LLM calls: 0 (None per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 0 prompt (0 cached), 0 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 5e-06 USD (0 model, 5e-06 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 0 (0 spoken); ended by 
- End of caller speech to first bot audio with sound, ms: p50 None, p95 None, max None (n=0)
- End of caller speech to first bot marker, ms: p50 None, p95 None, max None (n=0)
- First end marker per turn, ms: rasa_processing p50 None, p95 None, max None (n=0); tts_first_byte p50 None, p95 None, max None (n=0); tts_complete p50 None, p95 None, max None (n=0)
- Mantle latency_breakdown (0 turns): 
- Speech-to-text: 0 spoken turns, WER mean None, 0 heard nothing, 0 split into more than one user event
- Checked tokens: 
- Speech usage: 0.0 s streamed to speech-to-text, 0 characters of bot text (upper bound for text-to-speech); 5e-06 + 0 = 5e-06 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| short-reply-yes | short-reply | FAIL | none |  | 0.0 |

## Failed checks

- `short-reply-yes`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `short-reply-yes`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `short-reply-yes`: driver error RuntimeError: no bot turn after caller turn (closed)

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
