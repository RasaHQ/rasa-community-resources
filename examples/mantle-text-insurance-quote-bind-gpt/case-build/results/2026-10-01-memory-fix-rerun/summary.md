# insurance-quote-bind-gpt-text: run summary

- Case: `insurance-quote-bind`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:13:10Z to 2026-10-01T23:25:01Z
- Conversations: 2 run, 2 passed, 0 failed
- Caller turns: 10; turn latency p50 4701.3 ms, p95 50225.4 ms, max 50225.4 ms
- LLM calls: 26 (2.6 per caller turn, 3 side-channel, 0 empty completions)
- Tokens: 85824 prompt (27136 cached), 1004 completion (of which 101 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; active_cover_claim: 2; policy_reference: 2
- Case metric bind_requests_with_effect: 2 over 2 tool results
- Server log events: harborcover.bind_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.337128 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-renters-buy | normal | pass | get_quote→found, request_underwritten_offer→offered, confirm_material_answers→awaiting_confirmation, confirm_material_answers→confirmed, bind_offer→awaiting_confirmation, bind_offer→succeeded/verified_fixture_receipt | 22495, 2758, 3559, 3981, 50225 | 0.182889 |
| correction-dog-after-offer | correction | pass | get_quote→found, request_underwritten_offer→offered, update_quote_answer→answer_updated, request_underwritten_offer→offered, confirm_material_answers→awaiting_confirmation, confirm_material_answers→confirmed, bind_offer→awaiting_confirmation, bind_offer→succeeded/verified_fixture_receipt | 11312, 6310, 1417, 6385, 4701 | 0.154239 |

Synthetic scenario: HarborCover and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. active_cover_claim (the case metric, read from bot text) and policy_reference are reported separately from pass/fail; a match after a succeeded bind with its policy number is a correct statement, so read them against the bind results.
