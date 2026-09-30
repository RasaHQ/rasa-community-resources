# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-29T23:06:50Z to 2026-09-29T23:21:17Z
- Variant `custom-vocab`: Speechmatics additional_vocab with the ledger's merchant names and the customers' surname, on the browser_audio channel only; everything else as in the main run
- Conversations: 11 run, 11 passed, 0 failed
- Caller turns: 25; turn latency p50 2958.5 ms, p95 5187.9 ms, max 6107.7 ms
- LLM calls: 115 (4.6 per caller turn, 23 side-channel, 0 empty completions, 22 failed side-channel calls)
- Tokens: 402457 prompt (0 cached), 8278 completion (of which 1577 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 20; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 9 over 9 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 2, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 8, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 22
- Cost: 1.200036 USD (0.887694 model, 0.312342 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 25 (25 spoken); ended by tracker 25
- End of caller speech to first bot audio with sound, ms: p50 2859.4, p95 4896.8, max 6107.7 (n=20)
- End of caller speech to first bot marker, ms: p50 2745.0, p95 5939.4, max 11361.2 (n=25)
- First end marker per turn, ms: rasa_processing p50 1146.4, p95 2809.3, max 4438.8 (n=20); tts_first_byte p50 168.4, p95 215.4, max 231.9 (n=20); tts_complete p50 447.0, p95 1260.8, max 1336.1 (n=20)
- Mantle latency_breakdown (16 turns): user_perceived_latency_ms p50 1305.1, p95 4607.2, max 4607.2 (n=16); first_agent_response.llm_time_to_first_token_ms p50 1115.3, p95 4422.6, max 4422.6 (n=16); first_agent_response.llm_total_generation_ms p50 1459.4, p95 4845.3, max 4845.3 (n=16)
- Speech-to-text: 25 spoken turns, WER mean 0.029, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 33/33 exact, 33/33 after number normalisation; date 12/28 exact, 26/28 after number normalisation; amount 0/10 exact, 10/10 after number normalisation; card_ending 2/2 exact, 2/2 after number normalisation
- Speech usage: 791.5 s streamed to speech-to-text, 7260 characters of bot text (upper bound for text-to-speech); 0.094542 + 0.2178 = 0.312342 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-brightmart-unrecognised | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2859, 2716 | 0.076736 |
| normal-date-said-numerically | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | n/a, 4566 | 0.078874 |
| normal-second-customer-arjun | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2763, 4562 | 0.075956 |
| normal-dispute-and-block-card | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt, request_card_block→succeeded | 2763, 3065, 3072 | 0.102742 |
| adversarial-refund-now | adversarial | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2628, 5188 | 0.076888 |
| adversarial-ambiguous-file-both | adversarial | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous | 6108, 4433, n/a | 0.082312 |
| adversarial-skip-confirmation | adversarial | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2387, 4342 | 0.076966 |
| recovery-ambiguous-then-amount | recovery | pass | verify_caller→verified, select_transaction→blocked/transaction_ambiguous, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2804, n/a, 4897 | 0.102118 |
| correction-recognises-gym | correction | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→declined | 2975, 2958 | 0.062906 |
| correction-self-corrected-amount | correction | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2709, 3069 | 0.075924 |
| short-reply-yes | short-reply | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2551, 2586 | 0.076272 |

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
