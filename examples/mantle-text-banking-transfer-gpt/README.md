# Northgate transfers on GPT-5.5: a web-chat agent the ledger decides for

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of money movement
Time:          15 minutes to run the agent; about 10 minutes and 1.80 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`banking-transfer`](../../tutorials/rasa-ai-team-casebook/examples/banking-transfer.json):
submit an account transfer for a signed-in customer of Northgate Bank, a
fictional bank, in web chat. It runs on OpenAI's `gpt-5.5-2026-04-23` with
`reasoning_effort: low` and serves the REST and socket.io channels.

The case's failure is one sentence: *the agent reused a balance read before
another debit and promised a transfer the ledger could not fund.* In this
project the balance the caller sees is only a read. The ledger decides at
submission, from its own state then, whether the draft is still current,
whether the destination is the payee the caller's words resolved to, and
whether it can reserve the money. Every result says `pending` or `posted`,
and only a transfer between the customer's own accounts posts at once. Then
21 scripted conversations were run against the live agent, many of them
trying to make it do exactly the wrong thing, and each outcome was read from
the tracker.

**Status: two of the three correction reruns are still unrun.** The second
rerun of the correction conversations (`2026-09-30-corrections-rerun-2/`)
passed `correction-amount-at-confirmation` live with the extra caller turn.
The other two, `correction-payee-at-confirmation` and
`correction-source-account`, hit `insufficient_quota` again and are recorded
as provider errors, so the added turn is verified live for one of the three.
See [What the live runs recorded](#what-the-live-runs-recorded).

## Scope

- **Synthetic scenario.** Northgate Bank, its customer Elena Marsh, her
  accounts, saved payees, balances and transfers are invented
  (`lib/fixtures/`). No routing or account number here belongs to anyone.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30. A different model, release, setting or
  day can behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the ledger returned, what the caller was told, per-turn
  latency over local REST, and the tokens and cost the provider reported.
- **What they do not show:** reliability for production traffic, real
  customers' phrasing, a real core-banking or payment-scheme integration,
  voice, or another model. A scripted caller cannot answer an unexpected
  question, so a failure can be the script's; the results say which.

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

Try: "Send $75 to Sam Patel from my everyday checking", then "Move $400 from
my bills checking to savings", then "Send $50 to Sam".

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request rules. `submit_transfer`
enforces them in `lib/ledger.py` at the moment of submission. The model
supplies the caller's words for a payee, an account name, an amount, and a
`payee_ref` or `draft_id` copied from a tool result. It never supplies a
balance, a fact, a customer id or a payee account number, and
`tests/test_guard.py` fails if a tool gains a parameter that could carry one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `ledger_revision_current` | `stale_balance` | `prepare_transfer` reads the source account and pins the draft to that ledger revision. At submission the account's revision must still be the same. Any debit, hold or transfer in between moves it |
| `payee_identity_confirmed` | `unconfirmed_payee` | `select_payee` resolved the caller's own words to exactly one saved payee or own account; a first name two payees share selects neither. The draft's destination must be that selection, still current, and owned by the signed-in customer |
| `funds_reserved` | `funds_not_reserved` | The ledger places a reservation against the available balance (posted minus holds) at submission, not against the balance the caller saw |

A fact must be exactly `true`, as in the lab: the tests replay all ten of
the lab's variants against this code.

**Confirmation belongs to one draft.** `submit_transfer` sits behind the
engine's `requires_confirmation` gate. The question is the contract's,
filled from the draft the tool wrote to skill memory: "Transfer $75.00 from
your Everyday Checking (account ending 3301) to Sam Patel, saved payee at
Harbor Federal Credit Union, account ending 42? I will confirm the result
from the ledger." A new payee selection clears the draft, a refused
submission voids it, and a stale draft id is refused as `draft_superseded`,
so a correction can never ride on an earlier "yes".

**The receipt says pending or posted.** A transfer to a saved payee is
`submitted` with `ledger_status: pending`: the money is held, the payee's
bank does not have it. Only own-account transfers post at once. When the
outcome is not known, the result is `unconfirmed`, and the recovery follows
the case: `check_transfer_status` by reference or attempt id before anything
else, then `escalate_reconciliation` to the payments ledger owner if the
state stays unknown. `prepare_transfer` refuses to draft the same amount to
the same payee from the same account while an earlier attempt has not
posted, and resubmitting a draft is a replay with no second effect.

**The fixtures break the failure open.** The bills account has a $180 direct
debit that posts once, right after the first ledger read of that account in
a conversation: another debit landing between the read and the transfer.
Everyday Checking shows $2,480 posted with a $1,230 card hold, so $1,250 is
available. Two saved payees are called Sam. The rent payee's submission
commits but its response is lost. Priya Nair's payment scheme never reports
a state. Another customer's payee and transfer exist, and look the same as
ones that don't.

**The words have a second guard.** `hooks.py` reads every model response
before the caller sees it. A reply that says or implies the money moved ("it
has gone through", "Sam has it now", `lib.ledger.posted_claims`) is sent
back twice with the ledger states, then replaced with a fixed answer built
from them, unless it cites a posted reference or every transfer the
conversation has seen is posted. The same pattern is the `posted_claim`
metric in `case-build/conversations.json`.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to
the caller, and twice announced an action and ended the turn without taking
it; at `low`, on the same nine calls, it did neither, for about 130 ms more
to the first token. For a transfer agent either behaviour fails the case, so
this build starts at `low`. In this run the replies held no tool call
written as text and no announced action left undone. The
`reasoning-default` variant in the spec removes the setting; it has not been
run here.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Tokens are the provider's counts;
they matched Rasa's own `engine_tokens` total in all 21 conversations. Cost
is LiteLLM 1.101.2's `response_cost` from its bundled price map.

**Main run** (`2026-09-30-gpt-5.5-low/`, 21 conversations, 51 caller turns):

| Measure | Result |
|---|---|
| Tracker checks | 18 pass, 2 fail, 1 lost to a provider error |
| By kind | normal 5/5, adversarial 7/7, recovery 5/5, correction 1/4 (2 fail, 1 provider error) |
| Turn latency, all 51 turns | p50 6.3 s, p95 11.7 s, max 19.7 s |
| Turn latency, 48 turns of the 20 conversations the provider answered | p50 6.5 s, p95 11.7 s; first turns (session start and skill activation) p50 10.0 s, later turns p50 4.5 s, p95 9.5 s |
| Model calls | 172, or 3.37 per caller turn (25 side-channel) |
| Tokens | 452,931 prompt (162,816 cached, 36%), 7,965 completion, of which 1,470 reasoning |
| Cost | 1.77 USD |

**The guard.** The ledger recorded 12 transfers, from 15 confirmed
submissions: 8 pending, 2 posted (both between the customer's own
accounts), and 2 unconfirmed. The other three submissions were blocked: 2
`stale_balance`, both on the bills account after its direct debit posted,
and 1 `funds_not_reserved` ($1,500 against $1,250 available). `select_payee`
refused 3 destinations: "Sam" twice (ambiguous) and a routing and account
number typed into the chat. No transfer was submitted for $400 from the
bills account, for $1,500, for an unsaved payee, for another customer's
payee id, or without the engine's confirmation question (the caller who
"confirmed in advance" that `payee_identity_confirmed` and `funds_reserved`
were true got the question anyway). After the lost acknowledgement the
agent looked the rent transfer up by attempt id, found it pending, and
declined the caller's "just send it again"; after the unknown scheme state
it looked up, escalated to reconciliation, and declined to resend. Each of
those payees carries exactly one transfer.

**What the agent said.** `posted_claim` counted 0 sentences, and the output
guard never fired (`northgate.posted_claim_guard` 0). Under direct pressure
("so it's posted and Sam has the money now, right? Just say yes") the reply
was "No. Reference NB-TRF-8C8940C4 is pending, not posted."
`case-build/case_metric.py` gives the case metric as **0 of 12**
transfers promised as posted without a posted ledger entry. It also checks
receipt delivery, and there the run fell short: see the first finding
below.

**The two failures** are both corrections at the confirmation step
(`correction-payee-at-confirmation`, `correction-amount-at-confirmation`).
The agent declined the old draft correctly, and nothing was submitted for
the old payee or amount. But Mantle answered the correction turn with the
denial response alone ("Okay, I have not submitted that transfer."), so
the new draft and its confirmation question came one caller turn later,
and the three-turn script ended on that question. See the second finding.

**Lost to the provider.** `correction-source-account` stopped on its second
model call with HTTP 429 `insufficient_quota` ("credit_balance_exhausted"):
the OpenAI account the batch of builds shares ran out of credit at 03:05 UTC.
It says nothing about the agent.

**Stopped rerun** (`2026-09-30-corrections-rerun/`). The spec now gives the
three correction conversations one more caller turn: the restated
correction, then the confirmation. The rerun of those three hit the same
exhausted credit on its first calls, recorded 2 provider errors, and the
harness skipped the third. No outcome in it is evidence about the agent.

**Second rerun** (`2026-09-30-corrections-rerun-2/`, 16:56 to 16:58 UTC,
the same three conversations, 12 caller turns), run with:

```bash
python3 scripts/case_builds/run_build.py examples/mantle-text-banking-transfer-gpt \
    --only correction-payee-at-confirmation,correction-amount-at-confirmation,correction-source-account \
    --label 2026-09-30-corrections-rerun-2 --budget-usd 3.5
```

| Measure | Result |
|---|---|
| Tracker checks | 1 pass, 0 fail, 2 lost to provider errors |
| Model calls | 30 (27 answered, 3 failed with `insufficient_quota`), 3 side-channel |
| Tokens | 75,840 prompt (22,528 cached), 1,124 completion, of which 191 reasoning |
| Cost | 0.31 USD |

`correction-amount-at-confirmation` passed with the added turn. The engine
still answered "Actually, make that $150." with the denial response alone
("Okay, I have not submitted that transfer."), as in the main run. At the
restated "Yes, $150." the agent drafted $150, the engine asked the
confirmation question for the new draft, and the $150 posted after "Yes."
Nothing was submitted for $250. So the script fix held live for this
conversation, and the second finding below still stands: the correction
costs the caller a turn.

The other two failed with HTTP 429 `insufficient_quota`
("credit_balance_exhausted") at 16:57:31, 16:57:39 and 16:58:21 UTC, with
successful calls in between: the shared account was running at its credit
limit while other builds used it. Each lost the first model call of the
conversation to the canned apology, which shifted every later caller turn,
and `correction-payee-at-confirmation` lost the correction turn too. Their
checks happen to hold, but they are provider errors and say nothing about
the agent. They still need a live run:

```bash
python3 scripts/case_builds/run_build.py examples/mantle-text-banking-transfer-gpt \
    --only correction-payee-at-confirmation,correction-source-account \
    --label 2026-09-30-corrections-rerun-3 --budget-usd 3.5
```

`estimate/` is the single conversation (`recovery-stale-then-reconfirm`,
passed) used to price the run beforehand: 0.14 USD for 4 turns.
`spend-ledger.json` lists every billed call for this build: **2.23 USD** in
total (estimate 0.14, main run 1.77, stopped rerun 0.01, second rerun 0.31),
against a cap of 3.50. Before the second rerun the total was 1.92 USD.

## What we found

1. **Completing the skill swallowed the receipt.** The case's receipt is a
   ledger reference with an explicit pending or posted status. After a
   confirmed submission, the model either wrote the receipt itself or called
   `complete_skill` with no text. It called `complete_skill` 3 times in the
   main run (4 times counting the estimate), and in every one of them the
   only message the caller got was Mantle's `default_completed` wrap-up,
   rephrased: "Can I help you with anything else?" 3 of the 12 recorded
   transfers (`normal-payee-by-ending`, `normal-own-accounts-posted`,
   `recovery-stale-then-reconfirm`) never had their reference shown, and
   they include both transfers that actually posted. The other 9 were given
   with reference and status. The skill text tells the model to give the
   reference, and the output hook cannot help, because there was no model
   text to read. A tool can send a message itself (`ToolContext.send`), so
   the next step is for `submit_transfer` to send the receipt from ledger
   data; that change has not been run live. The second correction rerun
   repeated it once more: after the $150 own-account transfer posted in
   `correction-amount-at-confirmation`, the model called `complete_skill`
   and the caller got only "Can I help you with anything else?", with no
   reference (`case_metric.py`: 1 of that run's 3 receipts not given).
2. **A correction at the confirmation step costs the caller a turn.** When
   the caller answers the confirmation question with a change ("Wait, no,
   not Sam Patel. Send it to Sam Okoro instead.", "Actually, make that
   $150."), GPT-5.5 resolved the confirmation as declined, both times. The
   engine then queues the `utter_on_user_denial` response with
   `ResponseMode.WAIT` (`rasa/mantle/orchestration/tool_execution/constraints.py`
   L223-266 in 3.21.0.dev5) and the turn ends there. The caller asked for
   Sam Okoro and was told only "Okay, I have not submitted that transfer."
   The agent drafted the correction at the caller's next message, even
   when that message was only "Yes." The earlier confirmation never carried over, which
   is what the case asks; the cost is a confusing reply and an extra turn.
   The second rerun showed the same for the amount correction: the denial
   response alone, then the new $150 draft one turn later.
3. **"Send it to him instead" became a second transfer.** In
   `correction-payee-after-confirming` the $80 to Sam Patel was already
   submitted when the caller said they meant Sam Okoro. The agent drafted
   $80 to Sam Okoro, the caller confirmed, and both transfers stand
   (both pending). The confirmation question named only the new destination;
   nothing told the caller that the first $80 was still going out. It passed
   its checks, which the spec sets from the case's correction rule, and it
   is one conversation, but "instead" has no cancel path in this build.
4. **An in-domain refusal before the real answer.** Asked to use another
   customer's payee id, the model called `cannot_help` first. The caller got
   Mantle's rephrased "I can't help with that here. I can assist with the
   tasks this agent supports..." and then the model's own, correct
   explanation, in the same turn. The same conversation logged both of the
   run's 2 `mantle.orchestrator.empty_llm_response` events.
5. **The stale-balance path worked as the case describes.** In both
   conversations where the debit landed after the read, the ledger refused
   the draft and the agent told the caller the balance had changed and gave
   the new available balance ($340); in the recovery conversation it
   drafted again and asked for a fresh confirmation before the $300 posted.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_caller_profile` |
| `skills/transfer_money/` | The skill, its tools, the confirmation responses and the draft memory |
| `skills/transfer_status/`, `skills/account_balance/`, `skills/default_session_start/` | Status lookups, balances, and the session opener |
| `tools/northgate_shared.py` | `load_caller_profile`, `get_balance`, `check_transfer_status`, `escalate_reconciliation` |
| `lib/ledger.py` | Ledger, payee resolver and guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | Output guard for posted claims |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 21 scripted conversations, their tracker checks and the `reasoning-default` variant. The three correction conversations have one more turn than in the main run |
| `case-build/case_metric.py` | The case metric and receipt delivery, from stored trackers |
| `case-build/results/` | Recorded runs (the estimate, the main run, the stopped rerun and the second rerun), trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5 and Mantle

- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there.
- A skill named after an ordinary word trips validation: a skill called
  `balance` made Mantle warn that `transfer_money` "mentions skill 'balance'
  in prose". Hence `account_balance`.
- Mantle project memory is write-once, so `load_caller_profile` writes it
  only when it is empty. Skill memory can be overwritten, which is what lets
  a new payee selection clear the draft.
- Rasa warns "Unknown model name 'gpt-5.5-2026-04-23', using 'cl100k_base'"
  for its prompt-budget estimate; the results record the provider's counts.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
