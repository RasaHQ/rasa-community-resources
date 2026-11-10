# banking-transfer-gpt-text: run summary

- Case: `banking-transfer`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T16:56:46Z to 2026-09-30T16:58:42Z
- Conversations: 3 run, 1 passed, 0 failed, 2 lost to provider errors
- Caller turns: 12; turn latency p50 4104.6 ms, p95 9794.1 ms, max 9794.1 ms
- LLM calls: 30 (2.5 per caller turn, 3 side-channel, 0 empty completions)
- Tokens: 75840 prompt (22528 cached), 1124 completion (of which 191 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; posted_claim: 0
- Case metric transfer_effects: 3 over 3 tool results
- Server log events: northgate.posted_claim_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 3, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.311544 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-payee-at-confirmation | correction | ERROR (provider) | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 1934, 8623, 1991, 5402 | 0.076773 |
| correction-amount-at-confirmation | correction | pass | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→declined, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 9794, 3640, 3314, 7749 | 0.143298 |
| correction-source-account | correction | ERROR (provider) | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 4105, 4007, 4566, 8496 | 0.091473 |

## Provider errors

- `correction-payee-at-confirmation`: 2 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `correction-source-account`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and ledger results from the tracker. posted_claim counts bot sentences that say or imply money has moved, whatever the ledger said; case-build/case_metric.py joins them to ledger states for the case metric. Neither decides pass or fail.
