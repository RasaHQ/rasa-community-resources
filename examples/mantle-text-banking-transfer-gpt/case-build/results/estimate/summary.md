# banking-transfer-gpt-text: run summary

- Case: `banking-transfer`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:56:52Z to 2026-09-30T02:57:56Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 5741.6 ms, p95 13831.3 ms, max 13831.3 ms
- LLM calls: 13 (3.25 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 38384 prompt (14336 cached), 482 completion (of which 42 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; posted_claim: 0
- Case metric transfer_effects: 1 over 2 tool results
- Server log events: northgate.posted_claim_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.141868 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-stale-then-reconfirm | recovery | pass | select_payee→selected, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→blocked/stale_balance, prepare_transfer→drafted, submit_transfer→awaiting_confirmation, submit_transfer→submitted | 12198, 5742, 3860, 13831 | 0.141868 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and ledger results from the tracker. posted_claim counts bot sentences that say or imply money has moved, whatever the ledger said; case-build/case_metric.py joins them to ledger states for the case metric. Neither decides pass or fail.
