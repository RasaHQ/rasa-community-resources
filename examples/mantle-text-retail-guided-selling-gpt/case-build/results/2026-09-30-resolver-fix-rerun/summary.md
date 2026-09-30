# retail-guided-selling-gpt-text: run summary

- Case: `retail-guided-selling`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:57:20Z to 2026-09-30T02:58:29Z
- Conversations: 2 run, 2 passed, 0 failed
- Caller turns: 4; turn latency p50 9056.2 ms, p95 11003.2 ms, max 11003.2 ms
- LLM calls: 18 (4.5 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 45579 prompt (26624 cached), 1064 completion (of which 107 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; fit_claim: 0
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.140007 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-device-change-dock | correction | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended, record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 11003, 8636 | 0.07385 |
| correction-pro-to-standard-case | correction | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended, record_requirements→recorded, recommend_product→blocked/availability_stale, recommend_product→blocked/compatibility_unverified | 9056, 9261 | 0.066157 |

Synthetic scenario: Willow Shop and its catalogue are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the fit_claim count is read from bot text and reported separately from pass/fail.
