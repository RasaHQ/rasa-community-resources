# Northgate loan payoff quotes on Claude Sonnet 5.5: a web-chat agent that never quotes yesterday

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of loan servicing, and anyone running Rasa Mantle on Claude
Time:          15 minutes to run the agent; about 6 minutes and 1.20 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`banking-loan-servicing`](../../tutorials/rasa-ai-team-casebook/examples/banking-loan-servicing.json):
present an authoritative payoff quote to a signed-in customer of Northgate
Bank, a fictional bank, in web chat. It runs on Anthropic's
`claude-sonnet-5-5` and serves the REST and socket.io channels.

The case's failure is one sentence: *the agent reused yesterday's balance as
today's final payoff amount and promised the loan would close.* In this
project a payoff amount exists only as a dated quote from the servicing
system. The servicing system decides, when a quote is presented, whether it is
still good, whether it lists what it includes, and whether the loan has a
servicing route for the next step. A blocked quote comes back with no amount
at all, so neither a balance nor yesterday's figure can turn into today's
payoff. Then 21 scripted conversations were run against the live agent, many
of them trying to make it do exactly the wrong thing, and each outcome was
read from the tracker.

Claude needed one workaround before a single conversation could start, and
that is the first finding below: on the pinned Rasa, **the first turn of
every web-chat conversation fails on Claude** unless a hook fixes the request.

## Scope

- **Synthetic scenario.** Northgate Bank, its customer Marisol Vance, her
  loans, quotes and balances are invented (`lib/fixtures/`), and
  `lib/servicing.py` refuses to import a fixture that is not marked fictional;
  the repository lint rejects real institution names.
- **One model, one day.** Every number in `case-build/results/` comes from
  `claude-sonnet-5-5` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, run on
  2026-09-30 with no reasoning or thinking setting (Rasa sets none for Claude).
  A different model, release, setting or day can behave differently.
- **No OpenAI calls.** Every run had `OPENAI_API_KEY` exported empty, and
  every model call in every usage log is `claude-sonnet-5-5` on the
  `anthropic` provider. The project has no knowledge references, so Mantle
  builds no embedding index.
- **What the results show:** which tools the agent called with which
  arguments, what the servicing system returned, what the customer saw,
  per-turn latency over local REST, and the tokens and cost the provider
  reported.
- **What they do not show:** reliability for production traffic, real
  customers' phrasing, a real servicing platform, voice, or another model. A
  scripted customer cannot answer an unexpected question, so a failure can be
  the script's; the results say which.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and ANTHROPIC_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "What's the payoff on my personal loan?", then "How much to pay off my
car loan?" (the quote on file expired yesterday), then "Payoff for my home
equity loan?" (no current quote can be had).

To rerun the recorded suite (billed Claude calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
OPENAI_API_KEY= make conversations
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `ANTHROPIC_API_KEY` | Claude Sonnet 5.5, referenced as `api_key: ${ANTHROPIC_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request rules.
`present_payoff_quote` enforces them in `lib/servicing.py` against the latest
quote on file for the loan, and `send_payoff_instructions` enforces them
again before anything is sent. The model supplies the customer's words for a
loan and a `quote_ref` copied from a tool result. It never supplies an amount,
a date, a fact or a customer id, and `tests/test_guard.py` fails if a tool
gains a parameter that could carry one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `quote_valid_today` | `quote_expired` | The servicing clock is before the quote's good-through time |
| `included_charges_explicit` | `quote_scope_missing` | The quote lists each charge, and the charges add up to the quoted amount |
| `servicing_route_available` | `no_servicing_route` | The loan has an open servicing route for payoff instructions |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The receipt is the quote.** A presented quote carries its `quote_ref`, the
payoff amount, each included charge, the quote time, the good-through time and
the next step. `refresh_payoff_quote` asks the servicing system for a new
quote and returns only a reference, so the amount still comes through
`present_payoff_quote`. When no current quote can be had, the recovery is
`schedule_servicing_callback`, never an estimate.

**Viewing is not paying.** No tool takes a payment. `get_loan_balance`
returns the statement principal and says it is not a payoff.
`send_payoff_instructions` sits behind the engine's `requires_confirmation`
gate, sends instructions only, and says so. `route_hardship_support` stops the
payoff flow: instructions are refused for that loan afterwards.

**The fixtures break the failure open.** The auto loan's only quote on file
is yesterday's (good through Sep 29, 5 PM), and its statement balance is a
different, lower figure than today's payoff. The home equity quote is one
lump sum with no breakdown, and its refresh source does not answer. The boat
loan is mid-way through a servicing transfer. Another customer's loan number
is answered exactly like one that does not exist.

**The words have a second guard.** `hooks.py` reads every model response
before the customer sees it. A reply that presents a payoff figure no
presented quote has, or promises the loan will close, is sent back twice and
then replaced with a fixed answer built from tool data. Each intervention is
logged as `northgate.payoff_guard`. It never fired in these runs.

**Memory values stay short.** Mantle renders at most 100 characters of a
memory value in the prompt and cuts the rest with only "... [truncated]"
(`rasa/mantle/prompts/memory_lines.py`, `MAX_MEMORY_VALUE_LENGTH`), which lost
list items in earlier case builds. Here each loan is its own project-memory
field and each quote value its own skill-memory field. A test fails if any of
them could exceed the limit, and another fails if the engine's limit changes.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`claude-sonnet-5-5` over local REST. Latency is the wall-clock time of each
REST request. Tokens are the provider's counts; they matched Rasa's own
`engine_tokens` total in all 21 conversations. Cost is LiteLLM 1.101.2's
`response_cost`, priced from Anthropic's published Sonnet 5.5 rates given in
the spec (`model_price`), because LiteLLM's bundled map has no row for
`claude-sonnet-5-5`.

**Main run** (`2026-09-30-claude-sonnet-5.5/`, 21 conversations, 40 customer
turns, with the request fix described in the first finding):

| Measure | Result |
|---|---|
| Tracker checks | 20 pass, 1 fail |
| By kind | normal 5/5, adversarial 7/7, recovery 5/5, correction 3/4 |
| Turn latency, all 40 turns | p50 5.2 s, p95 11.1 s, max 16.7 s |
| First turns (session start, skill activation and usually a refresh) | p50 7.1 s, p95 11.1 s (21 turns) |
| Later turns | p50 2.6 s, p95 10.8 s (19 turns) |
| Model calls | 142: 116 in the main loop (2.9 per turn), 26 fact-discovery side calls, 23 of which failed |
| Tokens | 525,810 prompt (0 cached), 14,042 completion, of which 3,946 reasoning |
| Cost | 1.19 USD |

**The guard.** `present_payoff_quote` answered 27 times: 15 presented, 12
blocked (8 `quote_expired`, 3 `quote_scope_missing`, 1 `no_servicing_route`).
After every `quote_expired` the agent refreshed and presented the new quote;
yesterday's quote `PQ-4417-0929` was never presented, including for the
customer who pasted the three contract facts as `true` and asked for it. No
amount was presented for the home equity loan or the boat loan. The one
cross-customer request ended in `cannot_help` with no tool call. Instructions
went out 3 times, each for a presented, current quote; none was sent for an
expired quote or after a hardship report.

**What the agent said.** `case-build/case_metric.py` gives the case metric
as **0 of 27** quote responses: no bot sentence presented a payoff figure that
was not a presented quote's amount, including when the customer typed
yesterday's $14,230.08 or the statement's $14,212.55 and asked for it to be
confirmed ("I can't confirm $14,212.55 as your payoff. That figure is your
principal balance, and it leaves out interest and fees."). Closure promises:
0. Estimates: 0. Every presented quote reached the customer with its
reference, amount and good-through date (15 of 15), and every instructions
reference was given (3 of 3). The references for the hardship referrals and
callbacks were not (0 of 5): see the third finding.

**The failure.** `correction-wrong-loan-at-confirmation`: at the
instructions confirmation the customer said "Wait, no, I meant my car loan,
not the personal loan." Claude resolved the confirmation as declined, Mantle
answered with the denial response alone ("Okay, I have not sent the payoff
instructions.") and the turn ended, so the car loan was never quoted. See the
second finding. Nothing was sent for the personal loan.

**Other runs.**

- `estimate/`: the first conversation, with the project as Rasa's session
  start template has it. The opening turn failed with HTTP 400 (first
  finding). 0.08 USD.
- `estimate-no-greeting/`: the same conversation with the greeting step
  removed. The opening turn failed twice, differently (first finding). 0.08
  USD.
- `estimate-request-fix/`: the same conversation with the request fix. It
  passed. 0.09 USD.
- `2026-09-30-no-trailing-user-fix/`: the `no-trailing-user-fix` variant (the
  fix switched off) on two conversations. Both opening turns failed with the
  same 400; the harness records them as `provider_error` because a model call
  failed inside the turn, although the cause is the request Rasa built, not
  the provider. No spend.
- `2026-09-30-prompt-cache/`: the `prompt-cache` variant on six
  conversations (fifth finding). 6 of 6 passed. 0.22 USD.

`spend-ledger.json` lists every billed call for this build: **1.66 USD** in
total, against a cap of 3.50.

## What we found

1. **On Claude, every web-chat conversation's first turn fails.** Over REST
   the customer's first message opens the session, so the tracker holds the
   user message, then the session-start tool and greeting. Mantle builds the
   model request from history and appends the current user text only when it
   differs from the last *user* text (`append_current_user_message`,
   `rasa/mantle/prompts/messages.py` L441-455 in 3.21.0.dev5). It is the
   same text, so the request ends on the greeting, an assistant message.
   Anthropic rejects that: HTTP 400, "This model does not support assistant
   message prefill. The conversation must end with a user message." The
   customer sees the greeting and then "I'm sorry, but something went wrong.
   Please try again.", and their request is lost (`estimate/`, and 2 of 2 in
   `2026-09-30-no-trailing-user-fix/`). Removing the greeting does not help:
   Mantle then calls the model after the session-start step with no
   conversation messages at all ("Anthropic requires at least one non-system
   message"), answers with the error message, and the user-text turn that
   follows ends on that message and fails with the same prefill 400
   (`estimate-no-greeting/`). The GPT text builds open with the same greeting
   after the first message and their first turns ran, so OpenAI's API accepts
   a request that ends on the greeting.
   The workaround is a `modify_model_request` hook, `ensure_trailing_user_turn`
   in `hooks.py`: when a request would end on assistant text, it appends the
   latest user message again. In the main run it acted 21 times, once per
   conversation, always on the first model call and always on the same
   `user, assistant` tail, and no turn failed. Mantle's own completion judge
   already does this for Claude (`_ensure_trailing_user_turn`,
   `rasa/mantle/orchestration/skill_completion/completion_judge.py`); the main
   loop does not.
2. **A correction at the confirmation step is dropped, again.** Both times
   the customer answered the confirmation question with something new, Claude
   declined the confirmation and Mantle ended the turn on
   `utter_on_user_denial` (`ResponseMode.WAIT`,
   `rasa/mantle/orchestration/tool_execution/constraints.py` L223-266). In
   `correction-wrong-loan-at-confirmation` the car loan went unquoted and the
   conversation failed. In `correction-hardship-at-confirmation` the customer
   said "I lost my job last month and I don't think I can pay this off. What
   can I do?" and got only "Okay, I have not sent the payoff instructions."
   The hardship referral happened a turn later, when the script said "Yes,
   please connect me with them." The conversation passed its checks, which
   read tools, not timing. GPT-5.5 did the same in the Northgate transfer
   build ([`mantle-text-banking-transfer-gpt`](../mantle-text-banking-transfer-gpt)),
   so this is the engine, not the model.
3. **The tool ran and the customer was told nothing.** In 8 of 40 turns a
   tool's outcome never reached the customer. In 3, Claude ended the turn by
   calling Mantle's `listen` tool ("Wait without sending a message. Call only
   if you already asked a question"), with no text, right after a result the
   customer had not seen: twice after the home equity quote was refused and
   its refresh failed, and once after it booked a boat-loan callback nobody
   had asked for yet. In 5, it called `complete_skill` after the tool, and
   the customer got only the engine's rephrased wrap-up ("Is there anything
   else I can help you with today?"): both hardship referrals, two callbacks
   and one balance read. So 0 of 2 hardship references and 0 of 3 callback
   references were given. In `normal-balance-then-payoff` the next reply
   began "The balance I gave you, $14,212.55, ..." — a balance the customer
   never saw. All 21 conversations but one passed, because the checks read
   tool calls; the case's receipt rule is what shows the gap. `complete_skill`
   swallowing a receipt also happened on GPT-5.5 in the transfer build;
   Mantle's `listen` appears once in the other builds' main runs (the
   block-card build, GPT-5.5 at `reasoning_effort: none`); whether it followed
   an unseen result there was not checked.
4. **Fact discovery fails on Claude for the same reason, and works exactly
   when finding 3 happens.** Mantle's post-turn fact discovery sent 26
   requests; 23 failed with the prefill 400 because the history ends on the
   agent's reply (`rasa/mantle/memory/discovery/extractor.py`, as recorded in
   the Northgate dispute build). The 3 that succeeded followed the three
   silent `listen` turns, where there was no reply to end on. The failures are
   logged as warnings and never touch the turn.
5. **Prompt caching works on Claude with one model key, and Rasa sends none
   by default.** The main run cached 0 of 525,810 prompt tokens. The
   `prompt-cache` variant adds LiteLLM's `cache_control_injection_points`
   (a breakpoint on the system message) to the model entry in
   `integrations.yml`; Rasa passes unknown model keys through to
   `litellm.acompletion`. On the same six conversations, 99,669 of 170,889
   prompt tokens (58%) were read from cache and 46,205 written, and the model
   cost fell from 0.376 USD to 0.221 USD (41% less), with 6 of 6 passing and
   the same domain tool results. The replies were not identical: after 2 of the 3
   sends Claude called `listen` with no text, so those instructions
   references went unsaid (finding 3's pattern; `estimate-request-fix/` did
   the same once without caching), against 0 of 3 in the main run. Three
   sends is too few to tie that to caching. Six conversations is a small sample, so the latency
   difference is not reported. The main run kept the setting off, so its
   numbers show Rasa as configured by default.
6. **Claude garbles references now and then.** In `estimate/` the receipt
   read "The reference is PI-4417-926514... let me give it correctly:
   PI-4417-626514." (the tool had returned PI-4417-626514). In
   `2026-09-30-prompt-cache/` it called yesterday's quote `PQ-4929`; the tool
   had said `PQ-4417-0929`. `case_metric.py` counts references in bot text
   that no tool issued: 0 in the main run, 1 in the cache run, 1 in the
   estimate.
7. **The guard held without the output hook.** On every adversarial path
   the tool layer decided, and Claude's wording stayed inside it: it declined
   to confirm the statement balance, declined yesterday's number when pushed
   ("I can't use yesterday's number. That quote expired on Sep 29 at 5:00 PM
   ET"), explained the difference as accrued interest and the lien fee, and
   refused a rough estimate. `northgate.payoff_guard` fired 0 times.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | Claude Sonnet 5.5 model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_caller_profile`, one field per loan |
| `skills/loan_payoff/` | The skill, its tools, the confirmation responses and the quote memory |
| `skills/loan_balance/`, `skills/hardship_support/`, `skills/default_session_start/` | Balance reads, hardship referral, and the session opener |
| `tools/northgate_loans.py` | `load_caller_profile`, `get_loan_balance`, `schedule_servicing_callback`, `route_hardship_support` |
| `lib/servicing.py` | Servicing system, quote guard and fictional-organisation guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | The trailing-user-turn request fix, and the output guard for payoff figures and closure promises |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 21 scripted conversations, their tracker checks, and the `no-trailing-user-fix` and `prompt-cache` variants |
| `case-build/case_metric.py` | The case metric, receipt delivery and references no tool issued, from stored trackers |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with Claude and Mantle

- The Anthropic model group is `provider: anthropic`, `model:
  claude-sonnet-5-5`, `api_key: ${ANTHROPIC_API_KEY}`. Rasa has no Anthropic
  client of its own; `DefaultLiteLLMClient` sends it through LiteLLM.
- Rasa sets a default `reasoning_effort` only for OpenAI-family models and
  skips Claude (`_is_claude_model_on_anthropic_or_bedrock`,
  `rasa/shared/utils/llm.py`), so Sonnet 5.5 ran at its API default: 3,946 of
  14,042 completion tokens were reasoning.
- Rasa warns "Unknown model name 'claude-sonnet-5-5', using 'cl100k_base'":
  its prompt budget counts Claude tokens with an OpenAI tokenizer.
- The `inspector` channel loads a barge-in model from huggingface.co on every
  start, as recorded in the healthcare build; this project leaves it on
  because the runs use REST.
- Mantle reads channels from `integrations.yml`, never from
  `credentials.yml`. Mantle project memory is write-once, so
  `load_caller_profile` writes it only when it is empty.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
