# Rasa Skills project: Amber Grid payment plans (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`payment-plan-authority`. Amber Grid is a fictional energy supplier.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`
(the matrix channel for this case is web chat).

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_customer_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `payment_plan` (with the acceptance
  gate on `accept_plan_offer`)
- `tools/amber_grid_session.py`: `load_customer_profile`
- `lib/plans.py`: the billing service, the case guard, the organisation
  allowlist, the receipts and the word patterns, no Rasa imports
- `lib/conversation.py`: reads the acceptance question and answer from events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against invented instalments, "resolved" claims
  and promised relief
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/plans.py` and decides at `accept_plan_offer`, from
  the billing service's state then. No tool takes an amount, a number of
  payments, a date, a customer id or a fact; `tests/test_guard.py` fails if
  one gains such a parameter. Recorded terms are copied from the billing
  service, never from memory or the model.
- A recorded plan never resolves the account. Keep `account_resolved: false`
  on every result.
- Skill memory (`plan_account`, `offer_tag`, `offer_terms`) is written only by
  the tools, one short field per value: Mantle cuts a memory value at 100
  characters in the prompt, silently. `tests/test_guard.py` checks every
  fixture offer and revision against the cap.
- The fixture's organisation must be the contract's own fictional supplier
  (`lib.plans.assert_fictional`, an allowlist). Never add a real company.
- Leave `utter_on_user_denial` unset on `accept_plan_offer`, so a correction
  given in answer to the acceptance question is handled in the same turn.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the word patterns in `case-build/conversations.json` identical to
  `lib/plans.py`; `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
