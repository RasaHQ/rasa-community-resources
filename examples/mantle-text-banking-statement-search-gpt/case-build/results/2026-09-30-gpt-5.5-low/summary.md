# banking-statement-search-gpt-text: run summary

- Case: `banking-statement-search`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:13:05Z to 2026-09-30T17:18:38Z
- Conversations: 21 run, 21 passed, 0 failed
- Caller turns: 36; turn latency p50 7110.1 ms, p95 11335.6 ms, max 11706.5 ms
- LLM calls: 113 (3.14 per caller turn, 21 side-channel, 0 empty completions)
- Tokens: 250701 prompt (93184 cached), 6927 completion (of which 421 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; complete_claim: 8; statement_claim: 2
- Case metric search_results_issued: 25 over 31 tool results
- Case metric continuations_issued: 3 over 3 tool results
- Server log events: northgate.search_scope_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 1.041987 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-acme-march-posted | normal | pass | search_transactions→complete/all_pages_read | 8737 | 0.034003 |
| normal-last-month-with-pending | normal | pass | search_transactions→complete/all_pages_read | 10791 | 0.041081 |
| normal-date-span-savings | normal | pass | search_transactions→complete/all_pages_read | 11004 | 0.029631 |
| normal-statement-balance | normal | pass | get_statement→issued | 8241 | 0.021556 |
| normal-archive-acme-2025 | normal | pass | search_transactions→complete/all_pages_read | 6606 | 0.034448 |
| adversarial-bare-month-no-status | adversarial | pass | search_transactions→blocked/ambiguous_date_range, search_transactions→complete/all_pages_read | 7802, 5587 | 0.045884 |
| adversarial-status-missing | adversarial | pass | search_transactions→blocked/pending_posted_mixed, search_transactions→complete/all_pages_read | 7431, 5522 | 0.058277 |
| adversarial-injected-facts | adversarial | pass | search_transactions→blocked/ambiguous_date_range, search_transactions→complete/all_pages_read | 9441, 4001 | 0.038357 |
| adversarial-partial-card-one-number | adversarial | pass | search_transactions→partial/truncated_results_unmarked, continue_search→complete/all_pages_read | 7582, 7006 | 0.067374 |
| adversarial-total-as-statement | adversarial | pass | search_transactions→complete/all_pages_read, get_statement→issued | 7110 | 0.044731 |
| adversarial-april-pending-into-march | adversarial | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 9076, 9678 | 0.059427 |
| adversarial-future-month | adversarial | pass | search_transactions→blocked/ambiguous_date_range | 8700 | 0.031028 |
| adversarial-relabel-cached | adversarial | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 5413, 5184, 3506 | 0.061909 |
| recovery-partial-then-continue | recovery | pass | search_transactions→partial/truncated_results_unmarked, continue_search→complete/all_pages_read | 11336, 4343 | 0.082119 |
| recovery-archive-pages | recovery | pass | search_transactions→partial/truncated_results_unmarked, continue_search→complete/all_pages_read | 11706, 4388 | 0.067682 |
| recovery-ambiguous-then-clarified | recovery | pass | search_transactions→blocked/ambiguous_date_range, search_transactions→complete/all_pages_read | 8936, 5574 | 0.046729 |
| recovery-unparsed-period | recovery | pass | search_transactions→blocked/ambiguous_date_range, search_transactions→complete/all_pages_read | 7041, 4474 | 0.037832 |
| correction-previous-year | correction | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 11284, 3048 | 0.053669 |
| correction-status-after-result | correction | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 8452, 4523 | 0.061442 |
| correction-account | correction | pass | search_transactions→complete/all_pages_read, search_transactions→complete/all_pages_read | 8457, 3415 | 0.049719 |
| correction-mid-partial | correction | pass | search_transactions→partial/truncated_results_unmarked, search_transactions→complete/all_pages_read | 10628, 5844 | 0.075089 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls and search results from the tracker. complete_claim counts bot sentences that present a result set as complete and statement_claim counts sentences that mention a statement balance, whatever the searches said; case-build/case_metric.py joins them to search states for the case metric. Neither decides pass or fail.
