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
| `case-build/conversations.json` | The 21 scripted conversations, their tracker checks and the `reasoning-default` variant |
| `case-build/case_metric.py` | The case metric and receipt delivery, from stored trackers |

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
