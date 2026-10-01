# banking-transfer-gpt-text: run summary

- Case: `banking-transfer`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:09:42Z to 2026-10-01T23:12:37Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 4573.3 ms, p95 16900.8 ms, max 16900.8 ms
- LLM calls: 10 (2.5 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 30470 prompt (8192 cached), 522 completion (of which 128 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; posted_claim: 0
- Case metric transfer_effects: 1 over 1 tool results
- Server log events: northgate.posted_claim_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.131146 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-source-account | correction | pass | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→declined, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 16901, 2308, 6704, 4573 | 0.131146 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and ledger results from the tracker. posted_claim counts bot sentences that say or imply money has moved, whatever the ledger said; case-build/case_metric.py joins them to ledger states for the case metric. Neither decides pass or fail.
