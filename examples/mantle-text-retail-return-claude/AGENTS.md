# Rasa Skills project: Willow Shop returns and exchanges (Claude Sonnet 5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`retail-return`. Willow Shop is a fictional retailer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider, no reasoning or caching setting. Channels: `rest`,
`socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the Anthropic model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `hooks.py`, `lib/turn_order.py`: a `modify_model_request` hook that ends
  every Claude request on the customer's side (see README, finding 1). Keep
  `ENABLED = True`; without it every conversation's first message fails
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/start_return/`: the skill, its tools, its confirmation response and
  the selection memory its tools write
- `skills/return_status/`: status of an existing return
- `tools/willowshop_returns.py`: `load_session_customer`,
  `check_return_status`, `route_returns_desk`
- `lib/returns.py`: orders, the returns service and the case guard, no Rasa
  imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard and hook tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/returns.py`. The model supplies an order number, an
  item description, a resolution word, a replacement description, a reference
  and a reason, never a fact. The customer is project memory; the selected item
  and the recorded choice are skill memory only tools write.
- The customer's return-or-exchange choice is read from their own latest
  message that names one. Never add a tool that lets the model set it.
- `submit_return_request` has an engine confirmation gate (`tool_constraints`
  in `skill.md`) that reads the contract's question back. It sets no
  `utter_on_user_denial`, so a declined confirmation hands the turn back to the
  model and a correction in the same message is not dropped (see README).
- A receipt keeps its stages apart. `refund_amount_usd` is always `None` and
  the refund stage is never more than `not_decided`.
- Each memory value is one short field under 100 characters. Mantle cuts
  longer values in the prompt without a log line; `tests/test_guard.py`
  checks every fixture.
- The fixture must mark the retailer and carrier `(fictional ...)`; the
  library refuses to load otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
