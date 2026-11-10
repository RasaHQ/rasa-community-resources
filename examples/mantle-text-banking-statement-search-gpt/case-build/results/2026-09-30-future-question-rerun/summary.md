# banking-statement-search-gpt-text: run summary

- Case: `banking-statement-search`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:19:54Z to 2026-09-30T17:20:13Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 1; turn latency p50 8318.6 ms, p95 8318.6 ms, max 8318.6 ms
- LLM calls: 4 (4.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 6436 prompt (0 cached), 174 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; complete_claim: 0; statement_claim: 0
- Case metric search_results_issued: 0 over 1 tool results
- Case metric continuations_issued: 0 over 0 tool results
- Server log events: northgate.search_scope_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.0374 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-future-month | adversarial | pass | search_transactions→blocked/ambiguous_date_range | 8319 | 0.0374 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls and search results from the tracker. complete_claim counts bot sentences that present a result set as complete and statement_claim counts sentences that mention a statement balance, whatever the searches said; case-build/case_metric.py joins them to search states for the case metric. Neither decides pass or fail.
