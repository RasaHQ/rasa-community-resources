# Rasa Skills project: Northgate Bank loan servicing (Claude Sonnet 5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`banking-loan-servicing`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider, no reasoning setting. Channels: `rest`, `socketio`,
`inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the Claude model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_caller_profile` only, one
  short field per loan
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `loan_payoff` (with the confirmation
  gate on `send_payoff_instructions`), `loan_balance`, `hardship_support`
- `tools/northgate_loans.py`: `load_caller_profile`, `get_loan_balance`,
  `schedule_servicing_callback`, `route_hardship_support`
- `lib/servicing.py`: the servicing system, the quote guard and the
  fictional-organisation guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: the trailing-user-turn request fix for Claude, and the output
  guard against unquoted payoff figures and closure promises
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- The guard lives in `lib/servicing.py` and decides when a quote is presented
  and again when instructions are sent, from servicing records then. The
  model supplies the caller's words for a loan and a `quote_ref` copied from a
  tool result; never an amount, a date, a fact or a customer id.
- A blocked presentation returns no amount. Never add a path that turns a
  balance, an expired quote or a figure the caller typed into a payoff.
- No tool takes a payment. Never add one here.
- Skill memory (`quote_ref`, `quote_loan`, `quote_amount`,
  `quote_good_through`) is written only by `present_payoff_quote`. Mantle
  renders at most 100 characters of a memory value; keep every value one
  short field (`tests/test_guard.py` checks it).
- The fixture must mark the bank `(fictional)` and name no real lender;
  `lib/servicing.py` refuses to import otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the `closure_promise` metric in `case-build/conversations.json` identical to
  `lib/servicing.py`; `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
