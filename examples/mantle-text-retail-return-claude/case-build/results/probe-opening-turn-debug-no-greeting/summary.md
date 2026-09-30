# retail-return-claude-text: run summary

- Case: `retail-return`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported n/a)
- Run: 2026-09-30T04:36:57Z to 2026-09-30T04:37:08Z
- Variant `no-greeting`: Session start binds the customer but sends no greeting, so the first main-loop request ends on the customer's message
- Conversations: 1 run, 0 passed, 0 failed, 1 lost to provider errors
- Caller turns: 1; turn latency p50 363.5 ms, p95 363.5 ms, max 363.5 ms
- LLM calls: 2 (2.0 per caller turn, 0 side-channel, 0 empty completions, 1 rejected in-turn calls matching engine_errors)
- Tokens: 0 prompt (0 cached), 0 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; refund_claim: 0
- Case metric labels_issued: 0 over 0 tool results
- Server log events: mantle.turn.failed 2, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0
- Cost: 0 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-final-sale | adversarial | ERROR (provider) | load_session_customer→None | 364 | 0 |

## Provider errors

- `adversarial-final-sale`: 2 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Willow Shop, its customers and orders are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; the refund_claim count is read from bot text and reported separately from pass/fail. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
