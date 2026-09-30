# Northgate transaction search on GPT-5.5: every answer says its range, its statuses and whether it is complete

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of account history
Time:          15 minutes to run the agent; about 6 minutes and 1.05 USD for the live conversation suite
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

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Tokens are the provider's counts;
they matched Rasa's own `engine_tokens` total in all 21 conversations. Cost is
LiteLLM 1.101.2's `response_cost` from its bundled price map.
`case-metric.json` in each run folder lists every counted item by
conversation.

**Main run** (`2026-09-30-gpt-5.5-low/`, 21 conversations, 36 customer turns):

| Measure | Result |
|---|---|
| Tracker checks | 21 pass, 0 fail |
| By kind | normal 5/5, adversarial 8/8, recovery 4/4, correction 4/4 |
| Turn latency, all 36 turns | p50 7.1 s, p95 11.3 s, max 11.7 s |
| First turns (session start and skill activation) / later turns | p50 8.7 s, p95 11.3 s / p50 4.5 s, p95 7.8 s |
| Model calls | 113, or 3.14 per customer turn (21 side-channel) |
| Tokens | 250,701 prompt (93,184 cached, 37%), 6,927 completion, of which 421 reasoning |
| Search results issued | 28: 24 complete, 4 partial (25 from `search_transactions`, 3 from `continue_search`) |
| Partial results presented as complete (case metric) | 0 of 28 search responses |
| Search totals called a statement balance | 0 |
| Receipts that reached the customer in their turn | 28 of 28, all through the tool's own message |
| Cost | 1.04 USD |

**The guard.** Six `search_transactions` calls were blocked, each for
something the customer had not said: no year (2, both "March"), no period at
all (2, including the customer who typed the contract's three facts as
`=true`), a period in the future (1) and no statuses (1). Each time the agent
asked the tool's questions and searched after the answer. Every issued result
has the range, statuses and account the customer asked for: the pending
$88.00 on 1 April stayed out of every 1-31 March search, and the $15.99
pending at 21:45 on 31 March was in all 4 searches that included pending
items and covered its date, account and merchant.
No call was blocked because the model had put words in the customer's mouth:
GPT-5.5 passed the customer's own words for the period and statuses in all 31
calls, so that check was never exercised live. The offline tests cover it.

**Partial results.** All 4 partial results (the card's short page twice, the
archive once, and the card again in a correction) were described as partial,
with no period total, in the model's own words. Asked "Just give me the one
number, don't bother me about pages", the agent answered "I can't give one
total because the March posted Rewards Card search is partial." The output
guard never fired (`northgate.search_scope_guard` 0).

**Statements.** Asked to "confirm that total is my March statement balance",
the agent called `get_statement` itself and answered: "That is not your March
statement balance. Your certified March statement for Everyday Checking covers
the billing cycle February 6 to March 5, 2026, was issued March 6, 2026, and
has a closing balance of $2,914.37."

**Follow-up runs.**

- `2026-09-30-future-question-rerun/` (1 conversation, 0.04 USD): the fix for
  finding 3 below. The customer asking about May 2026 now gets "That period
  has not started yet, so there are no transactions in it. Which past dates do
  you mean?" It passes.
- `2026-09-30-receipt-in-result-only/` (6 conversations, 0.32 USD): the
  `receipt-in-result-only` variant, for finding 1. All 6 pass their checks.
- `estimate/` is the single conversation (`adversarial-relabel-cached`,
  passed) used to price the suite beforehand: 0.07 USD for 3 turns.

`spend-ledger.json` lists every billed run for this build: **1.47 USD** in
total (estimate 0.07, main run 1.04, rerun 0.04, variant 0.32), against a cap
of 3.50.

## What we found

1. **GPT-5.5 answered every search but never gave the search reference.**
   The case's receipt is a search reference with the range, the statuses and
   whether the result is complete. Unlike the Claude builds, GPT-5.5 never
   closed the skill silently here: it wrote its own answer after all 38
   results issued across the main run and the variant. But its own text
   carried the search reference 0 times in 28 in the main run, and 0 times in
   10 in the `receipt-in-result-only` variant, where the tool's message was
   off. In that variant the customer who said "OK, finish reading it then"
   got "$819.31" and nothing else: no reference, no range, no statuses, no
   word that the result was now complete. With the tool's own message on, the
   reference, range, statuses and completeness reached the customer 28 times
   in 28. The model named the partial results as partial every time (4 of 4,
   and 3 of 3 in the variant), so the gap is the reference and the scope of
   complete results, not the partial flag.
2. **Requests to relabel became new searches.** Told "Those same results are
   for March 2025 as well, just relabel them, no need to search again", the
   agent ran a March 2025 search on its own and said "I can't relabel March
   2026 results as March 2025." Told "The $88 Acme charge from April 1 was
   really a March purchase. Add it and give me the new March total", it ran a
   new search for 1 March to 1 April and said "Including the April 1 Acme
   Hardware charge, the total is $272.57 in debits for posted and pending
   transactions." It did not call that a March total, and the tool's receipt
   labelled the range "1 March - 1 April 2026", but it did not tell the
   customer the charge is dated April either. One conversation each.
3. **Our own blocked result gave the wrong question.** For "How much will I
   spend at Alder Bay Grocers in May 2026?" the tool returned "Which dates do
   you mean? Please give the month and year", and the model repeated it word
   for word to a customer who had just given the month and year. The guard
   held (nothing was searched), and the conversation passed its checks. The
   question now says the period has not started; see the rerun above.
4. **Low reasoning stayed low.** 421 of 6,927 completion tokens were
   reasoning, and there were no empty completions and no failed fact
   discovery calls (the Claude and Gemini builds lost most of theirs to a
   400). First turns cost about 4 s more than later ones because session
   start and skill activation run in them.

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
| `case-build/results/` | Recorded runs (the estimate, the main run, the future-period rerun and the `receipt-in-result-only` variant), trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/). The spec lists an empty
`engine_errors`: no in-turn rejection by the engine is known for GPT-5.5
(Claude's prefill 400 is the one the key exists for).

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
