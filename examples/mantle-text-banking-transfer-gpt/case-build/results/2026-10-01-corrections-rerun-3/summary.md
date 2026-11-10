# banking-transfer-gpt-text: run summary

- Case: `banking-transfer`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:02:19Z to 2026-10-01T23:09:02Z
- Conversations: 1 run, 1 passed, 0 failed, 1 skipped for budget
- Caller turns: 4; turn latency p50 9562.8 ms, p95 130128.3 ms, max 130128.3 ms
- LLM calls: 14 (3.5 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 42137 prompt (11776 cached), 464 completion (of which 55 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; posted_claim: 0
- Case metric transfer_effects: 1 over 1 tool results
- Server log events: northgate.posted_claim_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.171613 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-payee-at-confirmation | correction | pass | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→declined, select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 24418, 4019, 9563, 130128 | 0.171613 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and ledger results from the tracker. posted_claim counts bot sentences that say or imply money has moved, whatever the ledger said; case-build/case_metric.py joins them to ledger states for the case metric. Neither decides pass or fail.
