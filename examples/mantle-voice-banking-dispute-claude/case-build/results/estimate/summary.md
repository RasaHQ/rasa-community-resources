# banking-dispute-claude-voice: run summary

- Case: `banking-dispute`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-29T22:35:33Z to 2026-09-29T22:37:03Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 2400.4 ms, p95 4717.3 ms, max 4717.3 ms
- LLM calls: 10 (5.0 per caller turn, 2 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 34989 prompt (0 cached), 741 completion (of which 184 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 1; refund_promise: 0; fraud_finding: 0
- Case metric dispute_filings_with_effect: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, speechmatics.error 0, speechmatics.connection.failed 0, rime.connection.failed 0, rime.stream_audio.error 0, output_channel.response_delivery_failed 1, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2
- Cost: 0.104603 USD (0.077388 model, 0.027215 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 2 (2 spoken); ended by tracker 2
- End of caller speech to first bot audio with sound, ms: p50 2400.4, p95 4717.3, max 4717.3 (n=2)
- End of caller speech to first bot marker, ms: p50 2230.8, p95 4541.4, max 4541.4 (n=2)
- First end marker per turn, ms: rasa_processing p50 929.4, p95 3100.0, max 3100.0 (n=2); tts_first_byte p50 169.6, p95 176.1, max 176.1 (n=2); tts_complete p50 939.3, p95 1219.4, max 1219.4 (n=2)
- Mantle latency_breakdown (1 turns): user_perceived_latency_ms p50 1099.0, p95 1099.0, max 1099.0 (n=1); first_agent_response.llm_time_to_first_token_ms p50 900.2, p95 900.2, max 900.2 (n=1); first_agent_response.llm_total_generation_ms p50 3051.8, p95 3051.8, max 3051.8 (n=1)
- Speech-to-text: 2 spoken turns, WER mean 0.056, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 2/3 exact, 2/3 after number normalisation; date 1/3 exact, 3/3 after number normalisation; amount 0/1 exact, 1/1 after number normalisation
- Speech usage: 76.1 s streamed to speech-to-text, 604 characters of bot text (upper bound for text-to-speech); 0.009095 + 0.01812 = 0.027215 USD
- STT price: speechmatics realtime enhanced (operating_point: enhanced), language en, 0.00716667 USD per minute, from https://www.speechmatics.com/pricing (Pro, Real-time Enhanced: $0.43/hr, billed to the second; Real-time Standard $0.24/hr) on 2026-09-29
- TTS price: rime mistv3, speaker ironwood, 0.03 USD per 1,000 characters, from https://www.rime.ai/pricing (Starter, Mist v3: $0.03 / 1K characters; Coda $0.05 / 1K characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-brightmart-unrecognised | normal | pass | verify_caller→verified, select_transaction→selected, file_dispute→awaiting_confirmation, file_dispute→succeeded/verified_fixture_receipt | 2400, 4717 | 0.077388 |

Checks read the tracker's tool calls only, never reply wording. Refund and fraud wording in bot text is measured, not used for pass or fail. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included. The caller accent is instructed (gpt-4o-mini-tts, Indian English), not verified by a listener.
