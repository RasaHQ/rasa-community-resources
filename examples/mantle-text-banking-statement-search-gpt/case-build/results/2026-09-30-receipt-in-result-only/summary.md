# banking-statement-search-gpt-text: run summary

- Case: `banking-statement-search`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:20:22Z to 2026-09-30T17:21:55Z
- Variant `receipt-in-result-only`: The search tools do not send the customer the receipt themselves; it is only in the tool result
- Conversations: 6 run, 6 passed, 0 failed
- Caller turns: 10; turn latency p50 7324.7 ms, p95 9456.0 ms, max 9456.0 ms
- LLM calls: 32 (3.2 per caller turn, 6 side-channel, 0 empty completions)
- Tokens: 78038 prompt (29184 cached), 2029 completion (of which 41 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; complete_claim: 1; statement_claim: 0
- Case metric search_results_issued: 8 over 8 tool results
- Case metric continuations_issued: 2 over 2 tool results
- Server log events: northgate.search_scope_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.319732 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-acme-march-posted | normal | pass | search_transactions→complete/all_pages_read | 8763 | 0.025266 |
| normal-last-month-with-pending | normal | pass | search_transactions→complete/all_pages_read | 8138 | 0.042331 |
| adversarial-partial-card-one-number | adversarial | pass | search_transactions→partial/truncated_results_unmarked, continue_search→complete/all_pages_read | 8597, 3573 | 0.065574 |
| recovery-partial-then-continue | recovery | pass | search_transactions→partial/truncated_results_unmarked, continue_search→complete/all_pages_read | 8186, 5639 | 0.075927 |
| correction-previous-year | correction | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 7325, 4884 | 0.042992 |
| correction-mid-partial | correction | pass | search_transactions→partial/truncated_results_unmarked, search_transactions→complete/all_pages_read | 9456, 4206 | 0.067642 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls and search results from the tracker. complete_claim counts bot sentences that present a result set as complete and statement_claim counts sentences that mention a statement balance, whatever the searches said; case-build/case_metric.py joins them to search states for the case metric. Neither decides pass or fail.
