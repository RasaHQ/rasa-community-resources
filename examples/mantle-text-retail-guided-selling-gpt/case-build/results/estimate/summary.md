# retail-guided-selling-gpt-text: run summary

- Case: `retail-guided-selling`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:47:49Z to 2026-09-30T02:50:00Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 8561.4 ms, p95 12809.0 ms, max 12809.0 ms
- LLM calls: 8 (4.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 19617 prompt (9728 cached), 525 completion (of which 73 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; fit_claim: 0
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.070059 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-device-change-dock | correction | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended, record_requirements→recorded, recommend_product→recommended | 12809, 8561 | 0.070059 |

Synthetic scenario: Willow Shop and its catalogue are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the fit_claim count is read from bot text and reported separately from pass/fail.
