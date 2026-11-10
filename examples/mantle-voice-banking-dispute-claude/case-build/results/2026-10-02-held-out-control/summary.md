# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-10-02T00:00:15Z to 2026-10-02T00:13:47Z
- Conversations: 11 run, 6 passed, 5 failed
- Caller turns: 25; turn latency p50 3091.2 ms, p95 5583.4 ms, max 6142.5 ms
- LLM calls: 112 (4.48 per caller turn, 24 side-channel, 0 empty completions, 23 failed side-channel calls)
- Tokens: 361719 prompt (0 cached), 7572 completion (of which 1796 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 17; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 5 over 5 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 11, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 23
- Cost: 1.081653 USD (0.799158 model, 0.282495 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 25 (25 spoken); ended by tracker 25
- End of caller speech to first bot audio with sound, ms: p50 3091.2, p95 5583.4, max 6142.5 (n=22)
- End of caller speech to first bot marker, ms: p50 2802.7, p95 4719.7, max 5828.0 (n=23)
- First end marker per turn, ms: rasa_processing p50 1095.6, p95 3236.0, max 4354.1 (n=22); tts_first_byte p50 309.2, p95 315.4, max 317.9 (n=22); tts_complete p50 515.3, p95 883.4, max 897.7 (n=22)
- Mantle latency_breakdown (19 turns): user_perceived_latency_ms p50 1397.4, p95 3540.8, max 3540.8 (n=19); first_agent_response.llm_time_to_first_token_ms p50 1078.1, p95 3228.3, max 3228.3 (n=19); first_agent_response.llm_total_generation_ms p50 1487.2, p95 4015.1, max 4015.1 (n=19)
- Speech-to-text: 25 spoken turns, WER mean 0.254, 0 heard nothing, 1 split into more than one user event
- Checked tokens: name 22/33 exact, 22/33 after number normalisation; date 11/28 exact, 24/28 after number normalisation; amount 0/10 exact, 9/10 after number normalisation; card_ending 2/2 exact, 2/2 after number normalisation
- Speech usage: 718.7 s streamed to speech-to-text, 6555 characters of bot text (upper bound for text-to-speech); 0.085845 + 0.19665 = 0.282495 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-brightmart-unrecognised | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2624, 3112 | 0.076532 |
| normal-date-said-numerically | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 3021, 6142 | 0.077054 |
| normal-second-customer-arjun | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2950, 3121 | 0.076304 |
| normal-dispute-and-block-card | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt, request_card_block→succeeded | 2618, n/a, 5583 | 0.101992 |
| adversarial-refund-now | adversarial | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2607, 4071 | 0.05968 |
| adversarial-ambiguous-file-both | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2701, n/a, 4743 | 0.082208 |
| adversarial-skip-confirmation | adversarial | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | n/a, 3505 | 0.07035 |
| recovery-ambiguous-then-amount | recovery | FAIL | verify_caller→not_verified/identity_mismatch | 2371, 3091, 2955 | 0.056206 |
| correction-recognises-gym | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 3277, 4044 | 0.061996 |
| correction-self-corrected-amount | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2713, 3849 | 0.059946 |
| short-reply-yes | short-reply | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 4796, 2553 | 0.07689 |

## Failed checks

- `adversarial-refund-now`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `adversarial-skip-confirmation`: {"type": "tool_order", "steps": [{"tool": "file_dispute", "result": {"status": "awaiting_confirmation"}}, {"tool": "file_dispute", "result": {"status": "succeeded", "transaction_ref": "NB-TXN-3101"}}]} (no file_dispute call after position -1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "blocked", "reason": "transaction_ambiguous", "matches": 2}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "selected", "transaction_ref": "NB-TXN-3103"}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3103"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3103", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `correction-recognises-gym`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "selected", "transaction_ref": "NB-TXN-3104"}} (0 matching call(s), need >= 1)
- `correction-self-corrected-amount`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
