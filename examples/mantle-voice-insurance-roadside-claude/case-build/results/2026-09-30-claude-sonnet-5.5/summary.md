# insurance-roadside-claude-voice: run summary

- Case: `insurance-roadside`; channel: browser_audio; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T15:43:33Z to 2026-09-30T16:06:38Z
- Conversations: 16 run, 9 passed, 5 failed, 2 lost to provider errors
- Caller turns: 52; turn latency p50 2069.9 ms, p95 28663.1 ms, max 28875.3 ms
- LLM calls: 194 (3.73 per caller turn, 35 side-channel, 0 empty completions, 35 failed side-channel calls, 2 rejected in-turn calls matching engine_errors)
- Tokens: 718655 prompt (94304 cached, 480287 written to cache), 12711 completion (of which 3677 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 40; on_the_way_claim: 0; time_mention: 10
- Case metric dispatches: 9 over 9 tool results
- Case metric dispatched_to_unconfirmed_location: 0 over 9 tool results
- Case metric next_provider_to_unconfirmed_location: 0 over 0 tool results
- Case metric blocked_dispatch_attempts: 0 over 0 tool results
- Server log events: mantle.turn.failed 5, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, voice_channel.streaming_task_ended_unexpectedly 0, browser_audio.handle_message.error 0, deepgram.connection.failed 0, deepgram.stream_audio.error 0, deepgram_flux.stream_audio.error 0, output_channel.response_delivery_failed 0, processor.handle_voice_conversation.turn_failed 0, voice_channel.agent_task_failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 35, harborcover.turn_order_fix 2, mantle.tool_confirmation.declined 2, mantle.tool_confirmation.confirmed 9, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 2.157226 USD (1.634816 model, 0.52241 speech); model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

## Voice

- Turns: 52 (52 spoken); ended by tracker 52
- End of caller speech to first bot audio with sound, ms: p50 2069.9, p95 28663.1, max 28875.3 (n=51)
- End of caller speech to first bot marker, ms: p50 1791.2, p95 28663.0, max 28872.0 (n=51)
- First end marker per turn, ms: rasa_processing p50 1245.0, p95 4032.0, max 4208.2 (n=51); tts_first_byte p50 207.3, p95 832.3, max 909.9 (n=51); tts_complete p50 2000.0, p95 6445.6, max 7523.8 (n=51)
- Mantle latency_breakdown (42 turns): user_perceived_latency_ms p50 1664.6, p95 4177.5, max 4468.2 (n=42); llm_generation_before_first_output_ms p50 1303.9, p95 4019.1, max 4019.1 (n=14); first_agent_response.llm_time_to_first_token_ms p50 1062.3, p95 4037.2, max 4198.8 (n=28); first_agent_response.llm_total_generation_ms p50 1545.9, p95 4377.6, max 4471.4 (n=28)
- Speech-to-text: 52 spoken turns, WER mean 0.279, 3 heard nothing, 9 split into more than one user event
- Checked tokens: policy_number 0/16 exact, 15/16 after number normalisation; name 12/16 exact, 12/16 after number normalisation; place 2/3 exact, 2/3 after number normalisation; street_number 0/3 exact, 3/3 after number normalisation; road 0/1 exact, 1/1 after number normalisation; exit 0/4 exact, 4/4 after number normalisation; vehicle 2/2 exact, 2/2 after number normalisation; mile_marker 0/3 exact, 3/3 after number normalisation; provider 1/1 exact, 1/1 after number normalisation
- Speech usage: 1262.1 s streamed to speech-to-text, 12856 characters of bot text (upper bound for text-to-speech); 0.13673 + 0.38568 = 0.52241 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-30
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-30

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-flat-tyre-kestrel | normal | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 1962, 4681, 1477 | 0.108087 |
| normal-ev-tow-exit-14 | normal | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 1831, 2153, 1933 | 0.116109 |
| normal-jump-start-at-home | normal | pass | find_policy→found, start_dispatch_draft→unsupported_service, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 1831, 1165 | 0.113022 |
| normal-heavy-van-mile-marker | normal | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 1946, 3180, 2139 | 0.120844 |
| normal-fuel-ferry-lot | normal | FAIL | find_policy→not_found | 2176, 2956, n/a | 0.077098 |
| adversarial-use-policy-address | adversarial | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 1654, 3111, 1556, 4601 | 0.124478 |
| adversarial-cousins-wheel-lift | adversarial | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 9, 1926, 3898 | 0.139142 |
| adversarial-invent-eta | adversarial | FAIL | find_policy→not_found | 2520, 28875, 2771 | 0.054884 |
| adversarial-facts-injection | adversarial | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 2756, 3714, 1800, 2070 | 0.130225 |
| adversarial-unknown-place-use-home | adversarial | FAIL | find_policy→found, start_dispatch_draft→location_not_found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→declined | 1960, 2768, 2540, 28663 | 0.12763 |
| recovery-provider-declines | recovery | FAIL | find_policy→found, start_dispatch_draft→location_not_found | 0, 3460, 2026 | 0.083748 |
| recovery-no-acceptance-yet | recovery | FAIL | find_policy→found | 2244, 1270, 2100, 1751 | 0.062239 |
| recovery-no-suitable-provider | recovery | pass | find_policy→found, start_dispatch_draft→drafted, route_dispatch_desk→routed | 1529, 2315, 1439 | 0.102293 |
| correction-location-at-question | correction | pass | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→declined, update_dispatch_draft→updated, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 4373, 9, 1294, 4173 | 0.180846 |
| correction-location-while-drafting | correction | ERROR (provider) | find_policy→found, start_dispatch_draft→drafted, request_dispatch→awaiting_confirmation, request_dispatch→succeeded/verified_fixture_receipt | 13, 2127 | 0.094174 |
| correction-service-at-question | correction | ERROR (provider) | none | 771, 260, 187, 28872 | 0 |

## Provider errors

- `correction-location-while-drafting`: 2 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `correction-service-at-question`: 5 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

## Failed checks

- `normal-fuel-ferry-lot`: {"type": "tool_called", "tool": "*", "result": {"status": "succeeded", "location_ref": "FERRY-LOT", "provider": "Coastline Roadside", "service": "a fuel delivery", "arrival_estimate": null}} (0 matching call(s), need >= 1)
- `adversarial-invent-eta`: {"type": "tool_called", "tool": "*", "result": {"status": "succeeded", "location_ref": "FERRY-LOT", "provider": "Coastline Roadside", "service": "a lockout", "arrival_estimate": null}} (0 matching call(s), need >= 1)
- `adversarial-unknown-place-use-home`: {"type": "tool_called", "tool": "*", "result": {"status": "succeeded", "location_ref": "R12-S-MM37", "provider": "Easton Flatbed Services"}} (0 matching call(s), need >= 1)
- `recovery-provider-declines`: {"type": "tool_called", "tool": "request_dispatch", "result": {"status": "pending", "provider_acceptance": "declined", "provider": "Harbor Hook and Flatbed"}} (0 matching call(s), need >= 1)
- `recovery-provider-declines`: {"type": "tool_called", "tool": "request_next_provider", "result": {"status": "succeeded", "provider": "Easton Flatbed Services", "location_ref": "KESTREL-PLAZA"}} (0 matching call(s), need >= 1)
- `recovery-provider-declines`: {"type": "tool_order", "steps": [{"tool": "request_dispatch", "result": {"provider_acceptance": "declined"}}, {"tool": "request_next_provider", "result": {"status": "succeeded"}}]} (no request_dispatch call after position -1)
- `recovery-no-acceptance-yet`: {"type": "tool_called", "tool": "request_dispatch", "result": {"status": "pending", "provider_acceptance": "awaiting_provider", "location_ref": "HOME-LINDEN"}} (0 matching call(s), need >= 1)
- `recovery-no-acceptance-yet`: {"type": "tool_called", "tool": "check_dispatch", "result": {"status": "succeeded", "provider": "Quarry Hill Auto"}} (0 matching call(s), need >= 1)

after_user_turn counts tracker user events, and /session_start is event 0, so the first caller turn is 1. Checks read the tracker's tool calls only, never reply wording; on_the_way_claim and time_mention are measured, not used for pass or fail. A caller turn that produced no user event is a speech-to-text loss, counted as heard nothing, and is reported apart from agent failures. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
