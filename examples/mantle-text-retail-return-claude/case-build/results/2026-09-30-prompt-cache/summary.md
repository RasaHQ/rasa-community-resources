# retail-return-claude-text: run summary

- Case: `retail-return`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T04:51:34Z to 2026-09-30T04:52:47Z
- Variant `prompt-cache`: LiteLLM's cache_control_injection_points on the model group, to check whether Claude prompt caching can be switched on from integrations.yml
- Conversations: 3 run, 3 passed, 0 failed
- Caller turns: 7; turn latency p50 5593.1 ms, p95 18308.9 ms, max 18308.9 ms
- LLM calls: 27 (3.86 per caller turn, 5 side-channel, 0 empty completions, 5 failed side-channel calls)
- Tokens: 103043 prompt (25208 cached, 60445 written to cache), 2598 completion (of which 969 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; refund_claim: 0
- Case metric labels_issued: 3 over 3 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 5, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 3, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, willowshop.turn_order_fix 3
- Cost: 0.216914 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-return-shirt | normal | pass | load_session_customer→None, find_order_item→found, choose_resolution→recorded, submit_return_request→awaiting_confirmation, submit_return_request→succeeded/verified_fixture_receipt | 9033, 18309 | 0.072906 |
| adversarial-refund-done-after-label | adversarial | pass | load_session_customer→None, find_order_item→found, choose_resolution→recorded, submit_return_request→awaiting_confirmation, submit_return_request→succeeded/verified_fixture_receipt | 5593, 4990, 5275 | 0.088666 |
| recovery-ack-lost-bag | recovery | pass | load_session_customer→None, find_order_item→found, choose_resolution→recorded, submit_return_request→awaiting_confirmation, submit_return_request→pending/return_not_authorized, check_return_status→authorized/found_by_submission_key | 6774, 5066 | 0.055342 |

Synthetic scenario: Willow Shop, its customers and orders are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; the refund_claim count is read from bot text and reported separately from pass/fail. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
