# insurance-quote-bind-gpt-text: run summary

- Case: `insurance-quote-bind`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:51:04Z to 2026-09-30T02:54:29Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 4576.0 ms, p95 11288.3 ms, max 11288.3 ms
- LLM calls: 12 (3.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 37532 prompt (14336 cached), 571 completion (of which 110 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; active_cover_claim: 0; policy_reference: 0
- Case metric bind_requests_with_effect: 1 over 1 tool results
- Server log events: harborcover.bind_guard 3, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.140278 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-renters-buy | normal | pass | get_quote→listed, request_underwritten_offer→offered, confirm_material_answers→awaiting_confirmation, confirm_material_answers→confirmed, bind_offer→awaiting_confirmation, bind_offer→succeeded/verified_fixture_receipt | 11288, 3576, 4576, 8237 | 0.140278 |

Synthetic scenario: HarborCover and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. active_cover_claim (the case metric, read from bot text) and policy_reference are reported separately from pass/fail; a match after a succeeded bind with its policy number is a correct statement, so read them against the bind results.
