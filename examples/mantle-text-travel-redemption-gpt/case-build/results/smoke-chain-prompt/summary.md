# travel-redemption-gpt-text: run summary

- Case: `travel-redemption`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:56:18Z to 2026-09-30T02:56:52Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 3424.2 ms, p95 11498.5 ms, max 11498.5 ms
- LLM calls: 7 (3.5 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 18755 prompt (6144 cached), 283 completion (of which 21 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; booked_claim: 0
- Case metric unmatched_points_booking: 0 over 1 tool results
- Case metric points_debits: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0
- Cost: 0.074617 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-economy-lisbon | normal | pass | load_member_profile→None, search_reward_options→found, hold_reward→held, redeem_reward→awaiting_confirmation, redeem_reward→succeeded/verified_fixture_receipt | 11498, 3424 | 0.074617 |

Synthetic scenario: Horizon Travel, Horizon Rewards and all their data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker. unmatched_points_booking is the case metric (redemptions with unmatched points and booking state over redemption attempts); points_debits counts commits that moved points. booked_claim counts bot sentences that call something booked, from bot text, and never decides pass or fail.
