# Rasa Skills project: Amber Grid budget plans (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`utilities-budget-plan`. Amber Grid is a fictional energy supplier.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`
(the matrix channel for this case is web chat).

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_customer_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `budget_plan` (with the confirmation
  gate on `request_budget_option`)
- `tools/amber_grid_session.py`: `load_customer_profile`
- `lib/budget.py`: the billing service, the case guard, the organisation
  allowlist, the receipts and the word patterns, no Rasa imports
- `lib/conversation.py`: reads the confirmation question and answer from events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against budget estimates described as debt
  adjustments, promised relief and invented amounts
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/budget.py` and decides at `request_budget_option`,
  from the billing service's state then. No tool takes an amount, a number of
  payments, a date, a balance, a customer id or a fact; `tests/test_guard.py`
  fails if one gains such a parameter.
- No option changes the balance. Keep `balance_changed: false` and
  `debt_adjusted: false` on every result, and the schedule and the balance as
  separate fields and separate lines in the confirmation question and receipt.
- Skill memory (`plan_account`, `option_tag`, `option_schedule`,
  `option_basis`, `option_balance`) is written only by the tools, one short
  field per value: Mantle cuts a memory value at 100 characters in the
  prompt, silently. `tests/test_guard.py` checks every fixture option at every
  revision against the cap.
- The fixture's organisation must be the contract's own fictional supplier
  (`lib.budget.assert_fictional`, an allowlist). Never add a real company.
- Leave `utter_on_user_denial` unset on `request_budget_option`, so a
  correction given in answer to the question is handled in the same turn.
- Every apostrophe in a word pattern is the class `['’]`: GPT-5.5 writes
  typographic apostrophes.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the word patterns in `case-build/conversations.json` identical to
  `lib/budget.py`; `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
