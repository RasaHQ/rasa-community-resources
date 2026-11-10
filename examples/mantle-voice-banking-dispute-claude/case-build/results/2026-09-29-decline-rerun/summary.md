# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-29T23:21:58Z to 2026-09-29T23:24:42Z
- Conversations: 2 run, 1 passed, 1 failed
- Caller turns: 5; turn latency p50 5357.5 ms, p95 6379.6 ms, max 6379.6 ms
- LLM calls: 20 (4.0 per caller turn, 4 side-channel, 0 empty completions, 4 failed side-channel calls)
- Tokens: 68379 prompt (0 cached), 1604 completion (of which 535 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 5; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 4
- Cost: 0.207551 USD (0.152798 model, 0.054753 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 5 (5 spoken); ended by tracker 5
- End of caller speech to first bot audio with sound, ms: p50 5357.5, p95 6379.6, max 6379.6 (n=5)
- End of caller speech to first bot marker, ms: p50 4103.9, p95 5497.2, max 5497.2 (n=5)
- First end marker per turn, ms: rasa_processing p50 2386.2, p95 3708.9, max 3708.9 (n=5); tts_first_byte p50 167.9, p95 168.1, max 168.1 (n=5); tts_complete p50 441.1, p95 728.4, max 728.4 (n=5)
- Mantle latency_breakdown (4 turns): user_perceived_latency_ms p50 2153.1, p95 3876.9, max 3876.9 (n=4); first_agent_response.llm_time_to_first_token_ms p50 1962.9, p95 3696.5, max 3696.5 (n=4); first_agent_response.llm_total_generation_ms p50 2302.8, p95 4053.1, max 4053.1 (n=4)
- Speech-to-text: 5 spoken turns, WER mean 0.051, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 6/7 exact, 6/7 after number normalisation; date 2/4 exact, 4/4 after number normalisation; amount 1/2 exact, 2/2 after number normalisation
- Speech usage: 141.7 s streamed to speech-to-text, 1261 characters of bot text (upper bound for text-to-speech); 0.016923 + 0.03783 = 0.054753 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-unsure-at-confirmation | adversarial | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→declined | 3116, 3954 | 0.063676 |
| correction-other-charge-at-confirmation | correction | FAIL | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→declined, select_transaction→blocked/transaction_ambiguous | 5665, 5358, 6380 | 0.089122 |

## Failed checks

- `correction-other-charge-at-confirmation`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
