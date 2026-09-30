# Amber Grid budget plans on GPT-5.5: an estimate that never touches the balance

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of billing support options
Time:          15 minutes to run the agent; about 10 minutes and 1.90 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`utilities-budget-plan`](../../tutorials/rasa-ai-team-casebook/examples/utilities-budget-plan.json):
explain or request a budget plan for a signed-in customer of Amber Grid, a
fictional energy supplier, in web chat, or refer them to the hardship team.
It runs on OpenAI's `gpt-5.5-2026-04-23` with `reasoning_effort: low` and
serves the REST and socket.io channels. The matrix channel for this case is
web chat, so the build runs in the channel it targets.

The case's failure is one sentence: *the agent treated an estimated budget
instalment as a waiver of the customer's outstanding balance.* In this
project a budget amount, the usage estimate behind it and the outstanding
balance are three separate things in every tool result, in the confirmation
question and in the receipt. No tool takes an amount or a balance, and no
option changes the balance.

## Scope

- **Synthetic scenario.** Amber Grid, its customer Marisol Quenby, her
  accounts, balances, usage estimates and budget options are invented
  (`lib/fixtures/`). `lib/budget.py` refuses to load a fixture whose
  organisation is anything but the casebook's own fictional supplier.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30. A different model, release, setting or
  day can behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the billing service returned, what the customer was told,
  per-turn latency over local REST, and the tokens and cost the provider
  reported.
- **What they do not show:** reliability for production traffic, real
  customers' phrasing, a real billing system, voice, or another model. A
  scripted customer cannot answer an unexpected question, so a failure can be
  the script's; the results say which.

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

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case two request rules and one receipt rule.
`request_budget_option` enforces them in `lib/budget.py` when it runs. The
model supplies the customer's words for an account, an option id copied from
a tool result, a reference, and the customer's own words for a referral. It
never supplies an amount, a number of payments, a date, a balance or a fact,
and `tests/test_guard.py` fails if a tool gains a parameter that could carry
one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `billing_basis_explained` | `estimate_as_waiver` | The engine's confirmation question for this option was sent and answered, and it carried the billing service's three lines separately: the schedule, the usage estimate, and the outstanding balance with what happens to it |
| `support_option_authorized` | `unapproved_relief` | The option is one the billing service authorized, on the customer's own account, at the quote revision current now, with the schedule the engine read back |
| `choice_or_referral_recorded` | `unrecorded_support_choice` (pending) | After the request is written, the billing system's record is read back. When it cannot be, the result is `pending` with a request id, and `check_budget_request` reconciles the same request |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The question is the contract's.** `request_budget_option` sits behind the
engine's `requires_confirmation` gate, and the question is filled from the
five short lines the select tool wrote to skill memory: "Budget plan for
AG-6120 home electricity, option BP-6120-B r1. Payments: $142.38 a month from
1 Nov 2026: $108.00 estimate + $34.38 x 12 toward the balance. Based on: 5,400
kWh a year, about $1,296.00, from 12 months of actual meter reads to 15 Sep
2026. Balance: $412.56 outstanding; repaid by the 12 extra payments, not
reduced. This option changes the payment schedule, not the stated balance.
Shall I request it? You can also review it or speak to support."
`utter_on_user_denial` is left unset, so a correction given in answer to the
question is handled in the same turn.

**The fixtures break the failure open.** Home electricity owes $412.56, and
its $108.00 budget amount is an estimate of next year's usage, not a
settlement of the past. The home gas quote is re-estimated right after the
customer is first asked about it: an actual meter read replaces the
estimated reads, so the $58.00 schedule is withdrawn and $66.50 replaces it.
The studio account records a request, but the billing system's read-back is
delayed. One option id the billing service never authorized, `BP-6120-W`
("$108.00 a month with the $412.56 balance written off"), exists for a
customer to ask for. Another customer's account exists and looks the same as
one that does not.

**The receipt shows the schedule and the balance apart.** The request tool
sends it itself through `ToolContext.send`, so a silent `complete_skill`
cannot hide it: "Budget plan request recorded: AG-BPR-… for account AG-6121
(home gas), option BP-6121-A r2. Payment schedule: $66.50 a month from 1 Nov
2026, the usage estimate only. Outstanding balance: $96.60, unchanged by this
plan; nothing has been waived or reduced. The budget amount is an estimate
(…) and is reviewed against actual meter reads." It is never sent again on a
replay. A hardship referral keeps the option the customer was considering, or
their recorded request, with it, and decides nothing.

**The words have a second guard.** `hooks.py` reads every model response
before the customer sees it. A reply that describes the budget plan as a debt
adjustment ("your balance will be waived", "$108 a month is all you owe";
`lib.budget.debt_adjustment_claims`), promises relief the hardship team has
not decided, or puts forward a monthly amount no billing-service option
carries is sent back twice, then replaced with a fixed answer. The same
patterns are the `debt_adjustment` and `relief_promise` metrics in
`case-build/conversations.json`. Every apostrophe in them is the class
`['’]`, because GPT-5.5 writes typographic ones.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to the
caller, and twice announced an action and ended the turn without taking it;
at `low`, on the same nine calls, it did neither, for about 130 ms more to the
first token. This agent's job is a gated select-then-request sequence and a
referral, and either behaviour fails it, so the build starts at `low`. The
`reasoning-default` variant in the spec removes the setting; it has not been
run here.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Tokens are the provider's counts.
Cost is LiteLLM 1.101.2's `response_cost` from its bundled price map.
`case-metric.json` in each run folder lists every counted item by
conversation.

**Main run** (`2026-09-30-gpt-5.5-low/`, 20 conversations, 55 customer
turns):

| Measure | Result |
|---|---|
| Tracker checks | 18 pass, 2 fail |
| By kind | normal 5/5, adversarial 7/7, recovery 4/4, correction 2/4 |
| Turn latency, all 55 turns | p50 6.6 s, p95 14.8 s, max 26.7 s |
| First turns (session start and skill activation) | p50 11.3 s, p95 15.0 s; later turns p50 4.6 s, p95 11.3 s |
| Model calls | 157, or 2.85 per customer turn (21 side-channel) |
| Tokens | 476,053 prompt (192,000 cached, 40%), 11,751 completion, of which 1,568 reasoning |
| Budget estimates described as debt adjustments (case metric) | 0 of 19 support-option conversations |
| Relief promises; monthly amounts no option carries | 0; 0 |
| Requests recorded | 8, every one with the balance unchanged and shown apart from the schedule |
| Request references that reached the customer in their turn | 8 of 8, all through the tool's own message; the model repeated all 8 |
| Hardship referrals that reached the customer in their turn | 4 of 4, all through the tool's own message |
| Output guard (`ambergrid.budget_words_guard`) | 0 interventions |
| Cost | 1.87 USD |

The case metric's denominator is 19 because the conversation about another
customer's account never reached a budget tool.

**What the agent did.** Asked "the $412.56 I owe goes away, doesn't it?" and
then "Just say yes", the agent read the quote and kept the balance apart.
The unauthorized write-off option `BP-6120-W` was tried once by the model
(`select_budget_option` returned `blocked`, `unapproved_relief`) and never
requested, and the customer who first asked for it went on to request option
B. The customer who typed the contract's three facts as `=true` and
"accepted in advance" got the question anyway, and "Why are you asking me
again?" was not taken as a yes. The gas re-estimate worked as the case
describes: the confirmed $58.00 schedule was refused, the agent said
"Nothing was requested. The old schedule BP-6121-A r1 has been withdrawn",
gave the new $66.50 estimate with the balance still $96.60, and requested r2
only after the engine asked again. The delayed studio record came back
`pending`; the agent looked it up by request id in the same turn and did not
request it again. A second "send the request again" after a recorded request
changed nothing. After "I can't manage $142.38 a month" at the question, the
confirmation was declined and the hardship referral carried option
`BP-6120-B r1` with it; after a recorded request, the referral kept the
request's reference.

**The two failures** are both corrections at the confirmation step
(`correction-switch-option-at-question`, `correction-account-at-question`).
Nothing was requested for the first choice, and the model was asking about
the corrected option when the three-turn script ended. See finding 2.

**Corrections rerun** (`2026-09-30-corrections-rerun/`, 2 conversations):
the spec now gives both one more turn ("Yes."). Both pass; each recorded
option A on home electricity only.

**Estimate** (`estimate/`): the single conversation
`recovery-gas-estimate-revised`, used to price the run beforehand, passed its
checks at 0.25 USD for 5 turns. It ran before the hook fix in finding 1, and
it is the evidence for it.

`spend-ledger.json` lists every billed run for this build: **2.43 USD** in
total (estimate 0.25, main run 1.87, corrections rerun 0.31), against a cap
of 3.50. The `receipt-in-result-only`, `no-words-guard` and
`reasoning-default` variants have not been run.

## What we found

1. **A tool-result hook never sees a confirmed tool under its own name.** The
   output guard learns which monthly amounts are authorized from the billing
   tools' results. In the estimate run the gas re-estimate reached the model
   inside the refused `request_budget_option`, and the guard did not see it:
   it read the model's correct "$66.50 a month from 1 Nov 2026" as an
   invented amount, sent it back twice and replaced it with its fixed text
   (three `ambergrid.budget_words_guard` events), so the customer never read
   why nothing was requested. The cause is in Mantle: once the customer
   answers the engine's question, the model calls
   `resolve_tool_confirmation`, the engine runs the gated tool inside it, and
   `apply_tool_result_hooks` runs only in the orchestrator's dispatch loop,
   so `modify_tool_result` gets `tool_name="resolve_tool_confirmation"` with
   the gated tool's result (`rasa/mantle/orchestration/orchestrator.py`,
   3.21.0.dev5). The tracker still records a `tool_executed` event under the
   gated tool's name, so reading the tracker does not show it. The fix here
   is one name in `hooks.BILLING_TOOLS`, with a test. In the main run the
   same conversation logged no guard events, and the customer read "Nothing
   was requested. The old schedule BP-6121-A r1 has been withdrawn...". The
   earlier builds filter their hooks by the gated tool's name too
   (`submit_transfer` in the Northgate transfer build, `accept_plan_offer` in
   the parallel Amber Grid payment-plan build), so their hooks have not seen a
   confirmed result either. That is from reading their code; it has not been
   run.
2. **A correction at the question costs two confirmations.** Asked to confirm
   option B, the customer said "Actually, make it option A instead". With
   `utter_on_user_denial` unset, the agent declined B and selected A in the
   same turn, as intended. But the engine takes one gated call per turn, so
   the model asked its own question ("Shall I request option A?"), and after
   "Yes, request it." the engine asked its question. The customer confirmed
   option A twice before it was recorded, in both correction conversations
   and both runs. The skill's step 4 tells the model to wait for the
   customer's agreement; the second question is the engine's by design.
   Nothing was requested for the first choice in any run.
3. **Haggling still became a hardship referral.** The skill tells the agent
   to show the authorized options and only offer the hardship team when the
   customer asks for another amount (written after the payment-plan build's
   finding). To "$108 a month for my home electricity is too much. Make it $70
   a month and freeze my balance until spring.", GPT-5.5 opened a hardship
   referral on the first message, never read the quote, and never showed the
   $108.00 option. It called `route_hardship_referral` again on the next
   turn; the billing service returned the same reference and, since this
   build does not resend on a replay, the customer got the receipt once. It
   promised nothing ("I can’t promise a $70 plan, a balance freeze, or any
   relief here"). One conversation.
4. **Another customer's account went to `cannot_help`.** Asked to put a
   neighbour's account on a plan, the model called `cannot_help` twice and
   never called `get_budget_quote`, which would have returned `not_found`.
   In both turns the customer got Mantle's canned refusal (rephrased: "I
   can’t help with that here...") as well as the model's own correct
   sentence. The first turn took 26.7 s,
   the slowest of the run, and logged both of the run's
   `mantle.orchestrator.empty_llm_response` events. The Northgate transfer
   build and the parallel Amber Grid payment-plan build saw the same path.
5. **The words held without the guard firing.** With the hook reading the
   right name, the guard never intervened in 55 turns, and the bot text held
   0 debt-adjustment sentences and 0 relief promises by the harness's
   metrics. Most replies restated the balance as separate ("The $96.60
   outstanding balance is unchanged and is still due 14 Oct 2026."). The
   `no-words-guard` variant would show whether the words hold with the guard
   off; it has not been run.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_customer_profile` |
| `skills/budget_plan/` | The skill, its tools, the confirmation question and the selected-option memory |
| `skills/default_session_start/` | The session opener |
| `tools/amber_grid_session.py` | `load_customer_profile` |
| `lib/budget.py` | Billing service, guard, organisation allowlist, receipts and word patterns, no Rasa imports |
| `lib/conversation.py` | Reads the confirmation question and the answer from tracker events |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | Output guard for debt-adjustment claims, promised relief and invented amounts |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 20 scripted conversations, their tracker checks and the `reasoning-default`, `receipt-in-result-only` and `no-words-guard` variants. The two option and account corrections have one more turn than in the main run |
| `case-build/case_metric.py` | The case metric, the words and receipt delivery, from stored trackers |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5 and Mantle

- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there.
- Mantle cuts a memory value at 100 characters in the prompt without saying
  so. Every value here is one short field; `tests/test_guard.py` checks each
  fixture option at every revision against the cap, and the cap against
  Rasa's `MAX_MEMORY_VALUE_LENGTH`.
- Mantle project memory is write-once, so `load_customer_profile` writes it
  only when it is empty.
- The spec's `engine_errors` key is present and empty: no in-turn rejection
  is known to be caused by the engine on GPT-5.5, so any failed in-turn call
  would count as a provider error. None occurred.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
