# Rasa Skills project: Willow Shop subscription changes (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`retail-loyalty`. Willow Shop is a fictional retailer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.
The matrix channel for this case is Telegram; with no bot token yet, the
build runs in web chat, and `integrations.yml` shows the `telegram` block.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_member_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `subscription_change` (with the
  confirmation gate on `apply_subscription_change`)
- `tools/willow_session.py`: `load_member_profile`
- `lib/subscriptions.py`: the subscription service, the case guard, the
  organisation allowlist, the receipts and the word checks, no Rasa imports
- `lib/conversation.py`: reads the confirmation question and answer from events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against dates and amounts no tool result gave
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/subscriptions.py` and decides at
  `apply_subscription_change`, from the subscription service's state then.
  No tool takes a date, an amount, a revision, a member id or a fact;
  `tests/test_guard.py` fails if one gains such a parameter. Effects and
  receipts are copied from the service, never from memory or the model.
- A pending change is never re-sent. Recovery is `check_change_status`,
  which reads the original request key and revision and sends no command.
- Skill memory (`change_subscription`, `change_tag`, `change_label`,
  `change_effective`, `change_entitlements`) is written only by
  `select_subscription_change`, one short field per value: Mantle cuts a
  memory value at 100 characters in the prompt, silently.
  `tests/test_guard.py` checks every fixture option against the cap.
- The fixture's organisation must be the contract's own fictional retailer
  (`lib.subscriptions.assert_fictional`, an allowlist). Never add a real
  company.
- Leave `utter_on_user_denial` unset on `apply_subscription_change`, so a
  correction given in answer to the confirmation question is handled in the
  same turn.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
