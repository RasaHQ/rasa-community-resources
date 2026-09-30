# insurance-policy-status-gemini-text: run summary

- Case: `insurance-policy-status`; channel: rest; model: `gemini/gemini-3.1-pro-preview` (provider reported gemini-3.1-pro-preview)
- Run: 2026-09-29T20:44:40Z to 2026-09-29T20:47:35Z
- Conversations: 5 run, 4 passed, 0 failed, 1 lost to provider errors
- Caller turns: 11; turn latency p50 12449.8 ms, p95 31674.4 ms, max 31674.4 ms
- LLM calls: 36 (3.27 per caller turn, 5 side-channel, 6 empty completions)
- Tokens: 86102 prompt (0 cached), 11586 completion (of which 9463 reasoning)
- Thought signatures sent back: 57 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; coverage_promise: 0
- Server log events: harborcover.coverage_guard 10, mantle.orchestrator.empty_llm_response 3, mantle.turn.failed 4
- Cost: 0.311236 USD; priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-claim-decided | normal | pass | get_claim_status→answered | 22397 | 0.045824 |
| normal-greeting-then-claim | normal | pass | get_claim_status→answered | 6180, 29377 | 0.071138 |
| normal-policy-then-claim | normal | pass | get_policy_status→answered, get_claim_status→answered | 13910, 22302 | 0.081442 |
| correction-decided-claim-then-home-loss | correction | pass | get_claim_status→answered, open_coverage_question→routed | 31674, 12450, 9590 | 0.112832 |
| correction-decided-claim-then-same-policy-loss | correction | ERROR (provider) | none | 198, 169, 187 | 0 |

## Provider errors

- `correction-decided-claim-then-same-policy-loss`: 3 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: HarborCover and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the coverage_promise count is the case metric, read from bot text, and is reported separately from pass/fail.
