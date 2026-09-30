# banking-transfer-gpt-text: run summary

- Case: `banking-transfer`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T03:07:37Z to 2026-09-30T03:08:04Z
- Conversations: 2 run, 0 passed, 0 failed, 2 lost to provider errors, 1 skipped for budget
- Caller turns: 8; turn latency p50 689.7 ms, p95 3533.3 ms, max 3533.3 ms
- LLM calls: 9 (1.12 per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 1682 prompt (0 cached), 40 completion (of which 19 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; posted_claim: 0
- Case metric transfer_effects: 0 over 0 tool results
- Server log events: northgate.posted_claim_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 8, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.00961 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-payee-at-confirmation | correction | ERROR (provider) | none | 892, 771, 797, 3533 | 0.00961 |
| correction-amount-at-confirmation | correction | ERROR (provider) | none | 520, 670, 690, 602 | 0 |

## Provider errors

- `correction-payee-at-confirmation`: 4 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `correction-amount-at-confirmation`: 4 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and ledger results from the tracker. posted_claim counts bot sentences that say or imply money has moved, whatever the ledger said; case-build/case_metric.py joins them to ledger states for the case metric. Neither decides pass or fail.
