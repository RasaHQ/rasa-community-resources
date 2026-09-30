# Main run stopped: OpenAI credit ran out (2026-09-30)

The full 16-call run started at 19:20 UTC. OpenAI refused 14 of the 15 model
calls it made with "You have no credits remaining" (LiteLLM
`MidStreamFallbackError` wrapping `APIError`, in the gitignored server log and
usage log). The OpenAI key is shared with other builds running the same day.
Following the programme rule for a quota refusal, the run was stopped by hand
during the second call. Nothing here says anything about the agent.

- `normal-later-flight-same-day`: every caller turn got Mantle's canned
  "I'm sorry, but something went wrong. Please try again." Its tracker is
  kept (`trackers/`). The one model call that succeeded is priced in the
  ledger (0.010005 USD).
- `normal-dublin-return-bare-yes`: all four model calls failed the same way;
  the harness wrote no tracker for it because it was interrupted.

The harness's own classification of call 1, recomputed offline from the
usage log with `harness.usage_for` and `harness.classify`, is
`provider_error` (3 failed in-turn calls); its console line prints only
PASS or FAIL. After two provider errors in a row the harness skips the rest
of a run, so it would have stopped after call 2 by itself. It was
interrupted by hand during call 2's settle time, before it wrote
`results.json`.

Spend is in `../spend-ledger.json`: the harness's entry for call 1 and a
bounded entry for call 2 (speech only; its model calls were refused).
