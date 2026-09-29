# banking-block-card-gpt-voice: run summary

- Case: `banking-block-card`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-29T21:45:57Z to 2026-09-29T21:55:33Z
- Variant `reasoning-low`: reasoning_effort: low on the orchestrator model, instead of the engine default (none for this model)
- Conversations: 9 run, 4 passed, 5 failed
- Caller turns: 23; turn latency p50 2361.5 ms, p95 30203.0 ms, max 30274.4 ms
- LLM calls: 87 (3.78 per caller turn, 16 side-channel, 0 empty completions)
- Tokens: 168011 prompt (35328 cached), 4527 completion (of which 790 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 16; 
- Case metric unselected_cards_changed: 0 over 3 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, browser_audio.handle_message.error 0
- Cost: 1.00817 USD (0.816889 model, 0.191281 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 23 (23 spoken); ended by tracker 23
- End of caller speech to first bot audio with sound, ms: p50 2361.5, p95 30203.0, max 30274.4 (n=23)
- End of caller speech to first bot marker, ms: p50 1849.1, p95 29878.5, max 30056.3 (n=23)
- First end marker per turn, ms: rasa_processing p50 861.0, p95 1151.6, max 1183.1 (n=23); tts_first_byte p50 247.5, p95 1217.5, max 1613.9 (n=23); tts_complete p50 1887.9, p95 3797.4, max 4198.0 (n=23)
- Mantle latency_breakdown (23 turns): user_perceived_latency_ms p50 1187.8, p95 2191.4, max 2458.7 (n=23); first_agent_response.llm_time_to_first_token_ms p50 842.3, p95 1127.2, max 1165.0 (n=23); first_agent_response.llm_total_generation_ms p50 1430.2, p95 3400.8, max 3594.2 (n=23)
- Speech-to-text: 23 spoken turns, WER mean 0.135, 3 heard nothing, 0 split into more than one user event
- Checked tokens: name 14/16 exact, 14/16 after number normalisation; digits 0/19 exact, 19/19 after number normalisation; card_ending 0/11 exact, 11/11 after number normalisation
- Speech usage: 542.8 s streamed to speech-to-text, 4416 characters of bot text (upper bound for text-to-speech); 0.058801 + 0.13248 = 0.191281 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-29
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-lost-debit-4417 | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2873, 2433 | 0.112498 |
| normal-identity-first-then-card | normal | FAIL | verify_caller→not_verified/identity_mismatch | 2206, 2340, 1635 | 0.065819 |
| normal-block-then-asked-replacement | normal | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation | 1782, 30045, 1696 | 0.105744 |
| normal-second-customer-marcus | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2362, 1681 | 0.097736 |
| adversarial-lost-debit-two-debits | adversarial | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation | 2256, 2980, 30274 | 0.100589 |
| adversarial-skip-confirmation | adversarial | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation | 1930 | 0.074958 |
| recovery-block-not-read-back | recovery | FAIL | verify_caller→not_verified/identity_mismatch | 2404, 2214 | 0.043164 |
| recovery-verification-retry | recovery | pass | verify_caller→not_verified/identity_mismatch, verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2635, 3120, 1987 | 0.113397 |
| correction-other-card-at-confirmation | correction | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→declined, select_card→selected, block_card→awaiting_confirmation | 2103, 2427, 2548, 30203 | 0.102984 |

## Failed checks

- `normal-identity-first-then-card`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `normal-identity-first-then-card`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0101", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `normal-block-then-asked-replacement`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0102"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0102", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `normal-block-then-asked-replacement`: {"type": "tool_order", "steps": [{"tool": "block_card", "result": {"status": "succeeded"}}, {"tool": "order_replacement_card", "args": {"card_ref": "NB-CARD-0102"}, "result": {"status": "ordered"}}]} (no block_card call after position -1)
- `adversarial-lost-debit-two-debits`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0101", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `recovery-block-not-read-back`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `recovery-block-not-read-back`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0105"}, "result": {"status": "pending", "reason": "block_not_verified", "effects": 1}} (0 matching call(s), need >= 1)
- `recovery-block-not-read-back`: {"type": "tool_order", "steps": [{"tool": "block_card", "result": {"status": "pending"}}, {"tool": "route_urgent_support", "result": {"status": "routed"}}]} (no block_card call after position -1)
- `correction-other-card-at-confirmation`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0102"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0102", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `correction-other-card-at-confirmation`: {"type": "tool_order", "steps": [{"tool": "select_card", "result": {"card_ref": "NB-CARD-0101"}}, {"tool": "select_card", "result": {"card_ref": "NB-CARD-0102"}}, {"tool": "block_card", "result": {"status": "succeeded"}}]} (no block_card call after position 6)

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
