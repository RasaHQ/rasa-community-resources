# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-10-01T23:42:52Z to 2026-10-02T00:00:15Z
- Variant `held-out-vocab`: Speechmatics additional_vocab with half of the ledger's merchant names (Saffron Table, Metro Cabs, Cinnabar Streaming: the last three merchants by transaction id) and no surname, run on calls whose merchants are in the other half (Brightmart Online, Lakeview Fuel, Hollins Fitness), to test whether a vocabulary helps names it does not list
- Conversations: 11 run, 6 passed, 5 failed
- Caller turns: 25; turn latency p50 2944.7 ms, p95 4422.5 ms, max 4673.8 ms
- LLM calls: 110 (4.4 per caller turn, 23 side-channel, 0 empty completions, 22 failed side-channel calls)
- Tokens: 360359 prompt (0 cached), 7703 completion (of which 1851 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 19; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 5 over 5 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 14, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 22
- Cost: 1.087777 USD (0.797748 model, 0.290029 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 25 (25 spoken); ended by tracker 25
- End of caller speech to first bot audio with sound, ms: p50 2944.7, p95 4422.5, max 4673.8 (n=23)
- End of caller speech to first bot marker, ms: p50 2642.0, p95 4363.7, max 5857.7 (n=24)
- First end marker per turn, ms: rasa_processing p50 1095.9, p95 2426.7, max 2918.4 (n=23); tts_first_byte p50 308.7, p95 333.5, max 441.0 (n=23); tts_complete p50 476.0, p95 1038.2, max 1325.6 (n=23)
- Mantle latency_breakdown (21 turns): user_perceived_latency_ms p50 1417.7, p95 2207.6, max 3228.7 (n=21); first_agent_response.llm_time_to_first_token_ms p50 1065.8, p95 1805.8, max 2896.4 (n=21); first_agent_response.llm_total_generation_ms p50 1607.0, p95 2376.6, max 3383.0 (n=21)
- Speech-to-text: 25 spoken turns, WER mean 0.256, 0 heard nothing, 1 split into more than one user event
- Checked tokens: name 22/33 exact, 22/33 after number normalisation; date 11/28 exact, 24/28 after number normalisation; amount 0/10 exact, 9/10 after number normalisation; card_ending 2/2 exact, 2/2 after number normalisation
- Speech usage: 747.4 s streamed to speech-to-text, 6692 characters of bot text (upper bound for text-to-speech); 0.089269 + 0.20076 = 0.290029 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-brightmart-unrecognised | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 3522, 4674 | 0.076784 |
| normal-date-said-numerically | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2646, 3544 | 0.076876 |
| normal-second-customer-arjun | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2637, 2795 | 0.077058 |
| normal-dispute-and-block-card | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt, request_card_block→succeeded | 2667, 2956, 3487 | 0.10336 |
| adversarial-refund-now | adversarial | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2416, 3605 | 0.059864 |
| adversarial-ambiguous-file-both | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2911, 4422, n/a | 0.082638 |
| adversarial-skip-confirmation | adversarial | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | n/a, 3540 | 0.070812 |
| recovery-ambiguous-then-amount | recovery | FAIL | verify_caller→not_verified/identity_mismatch | 2678, 2915, 2997 | 0.05576 |
| correction-recognises-gym | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2699, 3443 | 0.062398 |
| correction-self-corrected-amount | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2945, 3464 | 0.0561 |
| short-reply-yes | short-reply | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2777, 2416 | 0.076098 |

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
