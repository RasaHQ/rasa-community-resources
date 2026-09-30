# retail-guided-selling-gpt-text: run summary

- Case: `retail-guided-selling`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T03:03:56Z to 2026-09-30T03:05:21Z
- Conversations: 5 run, 5 passed, 0 failed
- Caller turns: 5; turn latency p50 10759.7 ms, p95 11411.8 ms, max 11411.8 ms
- LLM calls: 25 (5.0 per caller turn, 5 side-channel, 0 empty completions)
- Tokens: 50021 prompt (23040 cached), 1499 completion (of which 151 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; fit_claim: 0
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.191395 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-dock-lumen7 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 11308 | 0.039079 |
| normal-case-lumen7-pro | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 9622 | 0.038309 |
| normal-cable-lumen6 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 10760 | 0.038054 |
| normal-wireless-lumen7 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 11412 | 0.036654 |
| normal-dock-lumen7-lite | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 9202 | 0.039299 |

Synthetic scenario: Willow Shop and its catalogue are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the fit_claim count is read from bot text and reported separately from pass/fail.
