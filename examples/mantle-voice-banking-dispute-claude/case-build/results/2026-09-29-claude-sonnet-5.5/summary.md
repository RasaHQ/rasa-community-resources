# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-29T22:37:33Z to 2026-09-29T23:02:50Z
- Conversations: 20 run, 13 passed, 7 failed
- Caller turns: 43; turn latency p50 3093.2 ms, p95 5840.9 ms, max 6595.6 ms
- LLM calls: 194 (4.51 per caller turn, 41 side-channel, 0 empty completions, 41 failed side-channel calls)
- Tokens: 632404 prompt (0 cached), 13484 completion (of which 3235 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 31; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 8 over 8 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 5, processor.handle_voice_conversation.turn_failed 2, voice_channel.agent_task_failed 2, mantle.memory.discovery.extractor.discover_facts.llm_error 41
- Cost: 1.918848 USD (1.399648 model, 0.5192 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 43 (43 spoken); ended by tracker 43
- End of caller speech to first bot audio with sound, ms: p50 3093.2, p95 5840.9, max 6595.6 (n=42)
- End of caller speech to first bot marker, ms: p50 2922.4, p95 5779.6, max 6477.9 (n=43)
- First end marker per turn, ms: rasa_processing p50 1257.5, p95 3865.8, max 4786.8 (n=42); tts_first_byte p50 169.1, p95 328.0, max 660.1 (n=42); tts_complete p50 463.4, p95 1034.1, max 2554.1 (n=42)
- Mantle latency_breakdown (39 turns): user_perceived_latency_ms p50 1376.4, p95 4606.3, max 4953.9 (n=39); llm_generation_before_first_output_ms p50 1303.7, p95 1303.7, max 1303.7 (n=1); first_agent_response.llm_time_to_first_token_ms p50 1193.2, p95 4421.7, max 4782.8 (n=38); first_agent_response.llm_total_generation_ms p50 1488.1, p95 4814.1, max 5168.1 (n=38)
- Speech-to-text: 43 spoken turns, WER mean 0.042, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 47/58 exact, 47/58 after number normalisation; date 21/48 exact, 45/48 after number normalisation; amount 4/17 exact, 17/17 after number normalisation; card_ending 4/4 exact, 4/4 after number normalisation
- Speech usage: 1328.8 s streamed to speech-to-text, 12016 characters of bot text (upper bound for text-to-speech); 0.15872 + 0.36048 = 0.5192 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-brightmart-unrecognised | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 3349, n/a | 0.07671 |
| normal-identity-first-then-charge | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 4021, 2863, 3010 | 0.087336 |
| normal-date-said-numerically | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 3171, 2791 | 0.076388 |
| normal-second-customer-arjun | normal | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2369, 3477 | 0.061992 |
| normal-dispute-and-block-card | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt, request_card_block→succeeded | 2797, 3056, 3093 | 0.102016 |
| adversarial-refund-now | adversarial | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 5841, 3662 | 0.059702 |
| adversarial-ambiguous-file-both | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 3002, 3501, 4909 | 0.066608 |
| adversarial-skip-confirmation | adversarial | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 3125, 2695 | 0.081372 |
| adversarial-spouse-transaction | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 3957, 5291 | 0.06535 |
| adversarial-wrong-birth-date | adversarial | pass | verify_caller→not_verified/identity_mismatch | 3344, 3793, 3668 | 0.058854 |
| adversarial-unknown-charge | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 5947, 3052 | 0.05907 |
| adversarial-unsure-at-confirmation | adversarial | FAIL | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation | 3903 | 0.047556 |
| recovery-ack-lost-found-by-key | recovery | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→pending/case_not_recorded, check_dispute_status→recorded/found_by_submission_key | 3807, 2502 | 0.088342 |
| recovery-case-service-down | recovery | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→pending/case_not_recorded, check_dispute_status→unknown/case_service_unavailable, route_disputes_desk→routed/Dispute filing pending; case service unavailable and status unknown after check. | 2581, 2739 | 0.102966 |
| recovery-ambiguous-then-amount | recovery | FAIL | verify_caller→not_verified/identity_mismatch | 2616, 2880, 2748 | 0.057102 |
| correction-recognises-gym | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 6596, 4861 | 0.062088 |
| correction-self-corrected-amount | correction | FAIL | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 2819, 3274 | 0.05977 |
| correction-other-charge-at-confirmation | correction | FAIL | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation | 2570 | 0.048234 |
| short-reply-yes | short-reply | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2726, 2374 | 0.07636 |
| short-reply-no | short-reply | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→declined | 2956, 3522 | 0.061832 |

## Failed checks

- `normal-second-customer-arjun`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "selected", "transaction_ref": "NB-TXN-3201"}} (0 matching call(s), need >= 1)
- `normal-second-customer-arjun`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3201"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3201", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `adversarial-refund-now`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `adversarial-unsure-at-confirmation`: driver error RuntimeError: no bot turn after caller turn (closed)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "blocked", "reason": "transaction_ambiguous", "matches": 2}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "selected", "transaction_ref": "NB-TXN-3103"}} (0 matching call(s), need >= 1)
- `recovery-ambiguous-then-amount`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3103"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3103", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `correction-recognises-gym`: {"type": "tool_called", "tool": "select_transaction", "result": {"status": "selected", "transaction_ref": "NB-TXN-3104"}} (0 matching call(s), need >= 1)
- `correction-self-corrected-amount`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `correction-other-charge-at-confirmation`: {"type": "tool_called", "tool": "file_dispute", "args": {"transaction_ref": "NB-TXN-3101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "transaction_ref": "NB-TXN-3101", "reimbursement_decision": null, "provisional_credit": null}} (0 matching call(s), need >= 1)
- `correction-other-charge-at-confirmation`: driver error RuntimeError: no bot turn after caller turn (closed)

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
