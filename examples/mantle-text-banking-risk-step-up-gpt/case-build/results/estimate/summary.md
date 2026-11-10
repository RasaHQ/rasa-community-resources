# banking-risk-step-up-gpt-text: run summary

- Case: `banking-risk-step-up`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:52:06Z to 2026-09-30T02:55:43Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 5; turn latency p50 9249.2 ms, p95 15006.0 ms, max 15006.0 ms
- LLM calls: 16 (3.2 per caller turn, 3 side-channel, 0 empty completions)
- Tokens: 42949 prompt (23040 cached), 554 completion (of which 51 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; sent_claim: 2
- Case metric transfers_sent: 1 over 1 tool results
- Case metric foreign_authorization_effects: 0 over 1 tool results
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0
- Cost: 0.127685 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-balance-then-changed-payee | normal | pass | get_balance→answered, assess_transfer→assessed, start_step_up→challenge_sent, submit_step_up_code→verified, submit_transfer→succeeded/verified_fixture_receipt | 9762, 9249, 3788, 5402, 15006 | 0.127685 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker. transfers_sent sums submit_transfer effects; foreign_authorization_effects is the case metric's numerator (transfers sent on a verification bound to a different assessment). sent_claim counts bot sentences saying a transfer went through and is reported separately from pass/fail.
