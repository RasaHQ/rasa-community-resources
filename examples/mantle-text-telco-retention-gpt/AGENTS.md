# Rasa Skills project: Juniper Mobile retention (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`telco-retention`. Juniper Mobile is a fictional mobile and broadband
provider.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.
The case's target channel is Telegram; `integrations.yml` shows the
`telegram` block to add once a bot token exists.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_customer_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `retention` (with the confirmation gate
  on `accept_retention_offer`), `account_status`
- `tools/juniper_retention.py`: `load_customer_profile`, `get_account_status`,
  `withdraw_contact`
- `lib/retention.py`: accounts, cancellation intake, offer catalogue, campaign
  dispatch, the case guard, the words patterns and the tool receipts, no Rasa
  imports
- `lib/conversation.py`: the customer's messages and the offer questions, from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against offers after a refusal and invented terms
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- The cancellation request is an independent intake. No offer rule gates
  `record_cancellation_request`, and no tool closes an account.
- The guard lives in `lib/retention.py` and decides twice: at
  `get_retention_offer` and at `accept_retention_offer`. The model supplies
  the customer's words for a service and an offer id copied from a tool
  result; never a price, a discount, a term, a fact, a customer id or an
  outcome.
- A refusal ends offers for the rest of the conversation, on every service.
  Keep `/stop` counted as the customer's words (`lib/conversation.py` drops
  only `/session_start`).
- Skill memory (`offer_*`) is written only by the tools, one short field per
  value under 100 characters; `tests/test_guard.py` checks every offer in the
  fixture.
- Any regex over customer or bot text reads straight and typographic
  apostrophes (GPT-5.5 writes `’`). Keep the `offer_prompt` and
  `closure_claim` metrics in `case-build/conversations.json` identical to
  `lib/retention.py`; the tests check them.
- `lib/retention.py` refuses fixtures whose organisation is not the
  casebook's fictional provider (an allowlist, not a list of real names).
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
