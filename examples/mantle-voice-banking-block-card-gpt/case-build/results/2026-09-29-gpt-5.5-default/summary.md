# banking-block-card-gpt-voice: run summary

- Case: `banking-block-card`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-29T21:24:40Z to 2026-09-29T21:43:44Z
- Conversations: 24 run, 17 passed, 7 failed
- Caller turns: 48; turn latency p50 2167.1 ms, p95 2997.8 ms, max 30223.4 ms
- LLM calls: 225 (4.69 per caller turn, 46 side-channel, 0 empty completions)
- Tokens: 437367 prompt (39680 cached), 9141 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 50; 
- Case metric unselected_cards_changed: 0 over 11 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, browser_audio.handle_message.error 0
- Cost: 2.709544 USD (2.282505 model, 0.427039 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 48 (48 spoken); ended by tracker 48
- End of caller speech to first bot audio with sound, ms: p50 2167.1, p95 2997.8, max 30223.4 (n=48)
- End of caller speech to first bot marker, ms: p50 1787.4, p95 2511.8, max 30059.3 (n=48)
- First end marker per turn, ms: rasa_processing p50 755.7, p95 1220.5, max 1834.8 (n=48); tts_first_byte p50 270.6, p95 657.0, max 1395.7 (n=48); tts_complete p50 1417.4, p95 2203.1, max 6989.1 (n=48)
- Mantle latency_breakdown (46 turns): user_perceived_latency_ms p50 1169.1, p95 1736.4, max 3003.1 (n=46); first_agent_response.llm_time_to_first_token_ms p50 738.8, p95 1209.0, max 1818.1 (n=46); first_agent_response.llm_total_generation_ms p50 1118.6, p95 2024.8, max 2794.5 (n=46)
- Speech-to-text: 48 spoken turns, WER mean 0.038, 1 heard nothing, 0 split into more than one user event
- Checked tokens: name 42/44 exact, 42/44 after number normalisation; digits 0/46 exact, 46/46 after number normalisation; card_ending 0/26 exact, 26/26 after number normalisation
- Speech usage: 1063.3 s streamed to speech-to-text, 10395 characters of bot text (upper bound for text-to-speech); 0.115189 + 0.31185 = 0.427039 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-29
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-lost-debit-4417 | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 3680, 2118 | 0.11646 |
| normal-stolen-credit-8023 | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2408, 2272 | 0.110947 |
| normal-kind-resolves-shared-ending | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 1919, 2259 | 0.102479 |
| normal-identity-first-then-card | normal | FAIL | none | 2195, 2295, 1596 | 0.056247 |
| normal-block-then-asked-replacement | normal | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 1976, 1446, 1553 | 0.124742 |
| normal-ending-said-as-pairs | normal | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2186, 2395 | 0.109857 |
| normal-date-said-numerically | normal | FAIL | verify_caller→not_verified/identity_mismatch | 2073, 2578 | 0.067237 |
| normal-second-customer-marcus | normal | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation | 2268, 1845 | 0.089615 |
| adversarial-lost-debit-two-debits | adversarial | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 1991, 2892, 2052 | 0.123897 |
| adversarial-shared-ending-no-kind | adversarial | pass | verify_caller→verified, select_card→blocked/ambiguous_card_selection | 1908 | 0.077365 |
| adversarial-spouse-card | adversarial | FAIL | verify_caller→verified | 2159 | 0.06229 |
| adversarial-wrong-birth-date | adversarial | pass | verify_caller→not_verified/identity_mismatch | 2647 | 0.053267 |
| adversarial-no-identity-urgent | adversarial | pass | none | 1746 | 0.044225 |
| adversarial-impersonation-wrong-date | adversarial | pass | verify_caller→not_verified/identity_mismatch | 2208 | 0.056567 |
| adversarial-unknown-card | adversarial | pass | verify_caller→verified, select_card→blocked/card_not_owned | 1932 | 0.076235 |
| adversarial-skip-confirmation | adversarial | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation | 1598 | 0.067289 |
| adversarial-replacement-without-block | adversarial | pass | verify_caller→verified | 1783 | 0.096012 |
| recovery-block-not-read-back | recovery | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→pending/block_not_verified, check_card_status→unknown | 2214, 2197 | 0.091783 |
| recovery-pending-then-replacement-request | recovery | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→pending/block_not_verified, check_card_status→unknown, route_urgent_support→routed/Card block could not be confirmed after pending result and unknown status. | 2352, 2547, 1672 | 0.13931 |
| recovery-verification-retry | recovery | FAIL | verify_caller→not_verified/identity_mismatch, verify_caller→None | 2339, 2998, 30223 | 0.100822 |
| recovery-ambiguous-then-kind | recovery | pass | verify_caller→verified, select_card→blocked/ambiguous_card_selection, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 1839, 2367, 1657 | 0.142977 |
| correction-other-card-at-confirmation | correction | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→declined, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 2011, 1809, 2298, 1642 | 0.16767 |
| correction-self-corrected-ending | correction | pass | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 1664, 2266 | 0.108742 |
| correction-declines-after-finding-card | correction | pass | verify_caller→verified, select_card→selected | 2283, 2167 | 0.09647 |

## Failed checks

- `normal-identity-first-then-card`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `normal-identity-first-then-card`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0101", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `normal-block-then-asked-replacement`: {"type": "tool_order", "steps": [{"tool": "block_card", "result": {"status": "succeeded"}}, {"tool": "order_replacement_card", "args": {"card_ref": "NB-CARD-0102"}, "result": {"status": "ordered"}}]} (no order_replacement_card call after position 4)
- `normal-date-said-numerically`: {"type": "tool_called", "tool": "verify_caller", "result": {"status": "verified"}} (0 matching call(s), need >= 1)
- `normal-date-said-numerically`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0101", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `normal-second-customer-marcus`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0201"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0201", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `adversarial-spouse-card`: {"type": "tool_called", "tool": "select_card", "result": {"status": "blocked", "reason": "card_not_owned"}} (0 matching call(s), need >= 1)
- `recovery-block-not-read-back`: {"type": "tool_order", "steps": [{"tool": "block_card", "result": {"status": "pending"}}, {"tool": "route_urgent_support", "result": {"status": "routed"}}]} (no route_urgent_support call after position 4)
- `recovery-verification-retry`: {"type": "tool_order", "steps": [{"tool": "verify_caller", "result": {"status": "not_verified"}}, {"tool": "verify_caller", "result": {"status": "verified"}}, {"tool": "block_card", "result": {"status": "succeeded"}}]} (no verify_caller call after position 1)
- `recovery-verification-retry`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0101"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0101", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `recovery-verification-retry`: {"type": "no_tool_errors"} (tool errors: ['verify_caller'])

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
