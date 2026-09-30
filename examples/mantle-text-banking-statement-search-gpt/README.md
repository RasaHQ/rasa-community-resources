# Northgate transaction search on GPT-5.5: every answer says its range, its statuses and whether it is complete

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of account history
Time:          15 minutes to run the agent; about 10 minutes and 1 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`banking-statement-search`](../../tutorials/rasa-ai-team-casebook/examples/banking-statement-search.json):
return a transaction-search result to a signed-in customer of Northgate Bank,
a fictional bank, in web chat. It runs on OpenAI's `gpt-5.5-2026-04-23` with
`reasoning_effort: low` and serves the REST and socket.io channels. Web chat
is the case's target channel, so nothing here stands in for another one.

The case's failure is one sentence: *a search for March spending included a
pending April item and presented the total as a statement balance.* In this
project a search result is issued only by a tool, for one range of dates and
the statuses the customer chose, both taken from the customer's own messages.
It says whether every page of the history was read, and a partial result has
no period total. Statements come from a separate tool and run on billing
cycles. Then 21 scripted conversations were run against the live agent, many
of them trying to make it do exactly the wrong thing, and each outcome was
read from the tracker.

## Scope

- **Synthetic scenario.** Northgate Bank, its customer Elena Marsh, her
  accounts, the merchants, amounts and statements are invented
  (`lib/fixtures/`). `lib/history.py` refuses to load a fixture whose
  organisation fields are not the casebook contract's own fictional bank
  marked `(fictional ...)`. It is an allowlist, not a list of real names.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30 over local REST.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the customer was shown, per-turn
  latency over local REST, and the tokens and cost the provider reported.
- **What they do not show:** reliability for production traffic, real
  customers' phrasing, a real core-banking history service, or another model.
  A scripted customer cannot answer an unexpected question, so a failure can
  be the script's; the results say which.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "What did I pay Acme in March?", then "This year, posted only", then
"Sorry, I meant last year". Then "List every posted transaction on my rewards
card in March 2026" and "keep going". The fixture's clock is 2 April 2026,
15:00 Eastern.

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`), then the
case metric (no spend):

```bash
make conversations
make metric RUN=2026-09-30-gpt-5.5-low
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request rules. `search_transactions`
enforces them in `lib/history.py` when it issues a result. The model supplies
the customer's words for the period and the statuses, an account, a merchant,
and a `search_ref` copied from a tool result. It never supplies a date range
of its own, a fact, a customer id or a total, and `tests/test_guard.py` fails
if a tool gains a parameter that could carry one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `date_range_confirmed` | `ambiguous_date_range` | The period resolves to exactly one range of dates in Eastern time, never past the fixture's clock. Every month, year, day and relative phrase in it must come from the customer's own messages, read from the tracker: "last year" grounds 2025 and "last month" grounds March 2026, but a model that writes "March 2026" for a customer who said "March" is refused. A month without a year is ambiguous on 2 April (March 2026 or March 2025), so the tool returns both and the question |
| `posting_status_explicit` | `pending_posted_mixed` | Posted only, pending only, or both, from the customer's own words. Until they say, the tool returns the contract's question: "Do you mean posted transactions during March 2026, or also pending items? I will label the result scope." |
| `result_scope_complete` | `truncated_results_unmarked` | Every page the history source holds for the query was read and none came back short. Otherwise the result is `partial`: it lists what was read, has no total, and carries a continuation for `continue_search`, which reads more of the same query and nothing else |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The receipt is sent by the tool.** The transfer, returns and claim builds
found that after a tool issues a receipt, the model often closes the skill
with no text of its own and the customer never sees the reference. Here
`search_transactions` and `continue_search` send the receipt themselves
through `ToolContext.send`, as the HarborCover claim build does: "Search
NB-SRCH-2F2A9A82: posted transactions only at Acme Hardware, all your
accounts, 1-31 March 2026 (Eastern time, by transaction date). Complete: yes,
all 2 matching transactions read. Debits $168.58, credits $0.00. This is a
search result, not a statement balance." A partial one says "Complete: no"
and has no amount in it. The `receipt-in-result-only` variant turns this off.

**The fixtures break the failure open.** A pending $88.00 Acme Hardware charge
on 1 April sits next to March. A pending $15.99 charge at 21:45 on 31 March is
already 1 April in UTC, and a coffee at 23:30 on 28 February is 1 March in
UTC; the search counts the first and not the second. The Rewards Card's
history service returns its second page cut short the first time it is asked.
The archive (before 1 April 2025) serves one page per request. Checking and
card statements run on billing cycles (6th to 5th, 13th to 12th), so "the
March statement" of the checking account ends on 5 March. Another customer's
$500.00 Acme charge exists and is never visible.

**The words have a second guard.** `hooks.py` reads every model response
before the customer sees it. While the latest search is partial, a reply that
presents a result set as complete ("in total", "that's all", "you spent
$700.00", `lib.history.complete_claims`) is sent back twice with the search
states, then replaced with a fixed answer built from them. The same happens to
a reply that calls a search total a statement balance.

**One short memory field per value.** Mantle cuts a memory value at 100
characters in the prompt without saying so (found in the GPT quote and
diagnostics builds). The last search is kept as three short fields, and a
test runs 1,000+ searches across periods, statuses, accounts and merchants and
fails if any value would pass 100 characters.

**No confirmation gate.** A search moves nothing, so no tool sits behind
`requires_confirmation`, and there is no `utter_on_user_denial` to swallow a
correction. The case's question comes from the guard's blocked result.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to the
caller, and twice announced an action and ended the turn without taking it;
at `low`, on the same nine calls, it did neither, for about 130 ms more to
the first token. This case turns on running a new search when the customer
changes the range, not announcing one, so this build starts at `low` like the
other GPT case builds. The `reasoning-default` variant in the spec removes the
setting; it has not been run here.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_caller_profile` |
| `skills/transaction_search/` | The skill, `search_transactions`, `continue_search` and the last-search memory |
| `skills/default_session_start/` | Binds the signed-in customer, then greets |
| `tools/northgate_history.py` | `load_caller_profile`, `get_statement` |
| `lib/history.py` | History source, period and status resolvers, guard, receipts, no Rasa imports |
| `lib/conversation.py` | The customer's own messages, from tracker events |
| `lib/fixtures/` | Fictional history and statements, and the vendored case contract |
| `hooks.py` | Output guard for partial-as-complete and statement-balance claims |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 21 scripted conversations, their tracker checks, and the `reasoning-default` and `receipt-in-result-only` variants |
| `case-build/case_metric.py` | The case metric and receipt delivery, from stored trackers |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/). The spec lists an empty
`engine_errors`: no in-turn rejection by the engine is known for GPT-5.5
(Claude's prefill 400 is the one the key exists for).

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
