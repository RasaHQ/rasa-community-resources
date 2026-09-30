# Rasa Skills project: Northgate Bank transaction search (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`banking-statement-search`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`
(web chat is the case's target channel).

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_caller_profile` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/transaction_search/`: the skill, `search_transactions`,
  `continue_search` and the last-search memory they write
- `tools/northgate_history.py`: `load_caller_profile`, `get_statement`
- `lib/history.py`: the paged history source, the period and status
  resolvers, the case guard and the receipts, no Rasa imports
- `lib/conversation.py`: the caller's own messages from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against presenting a partial search as complete
  or a search total as a statement balance
- `tests/`: offline guard, receipt, memory and hook tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/history.py` and decides when a result is issued.
  The model supplies the caller's words for the period and the statuses, an
  account, a merchant and a `search_ref` copied from a tool result; never a
  date range it made up, a fact, a customer id or a total.
- The period and statuses must come from the caller's own messages, read
  from the tracker (`context.events`). A month with no year the caller said
  is ambiguous; the tool asks, it never picks.
- A partial result has no period total. `continue_search` reads more of the
  same query; it never takes a new range or scope.
- Dates are the transaction's date in Eastern time, never the UTC date.
- `TOOL_SENDS_RECEIPT = True` in `lib/history.py`: the search tools send the
  receipt (reference, range, statuses, complete or not) through
  `ToolContext.send`. Keep it on; the `receipt-in-result-only` variant shows
  what happens without it.
- No tool has a confirmation gate: a search moves nothing, and the case's
  question comes from the guard's blocked result. There is therefore no
  `utter_on_user_denial`; do not add one if a gate is ever added, so a
  correction at a confirmation is answered in the same turn.
- Each memory value is one short field under 100 characters. Mantle cuts
  longer values in the prompt without a log line; `tests/test_guard.py`
  checks every combination.
- The fixture's organisation fields must be the casebook contract's own
  fictional bank, marked `(fictional ...)`; the library refuses to load
  otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the `complete_claim` metric in `case-build/conversations.json` identical to
  `lib/history.py`; `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
