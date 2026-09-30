# Rasa Skills project: HarborCover claim intake (Claude Sonnet 5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`insurance-file-claim`. HarborCover is a fictional insurer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider, no reasoning setting, prompt caching on the system
message. Channels: `rest`, `socketio`, `inspector`. Target channel: Microsoft
Teams (`botframework`), not enabled until a bot registration exists.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the Anthropic model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `hooks.py`, `lib/turn_order.py`: a `modify_model_request` hook that ends
  every Claude request on the customer's side. Keep `ENABLED = True`; without
  it every web-chat conversation's first message fails
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in policyholder, then greets
- `skills/file_claim/`: the skill, its tools, its confirmation response and
  the draft memory its tools write
- `skills/claim_status/`: status of a submitted report or an existing claim
- `tools/harborcover_claims.py`: `load_session_customer`,
  `check_claim_submission`, `route_claims_intake`
- `lib/claims.py`: policies, drafts, the attachment service, the claims
  system and the case guard, no Rasa imports
- `lib/conversation.py`: reads the customer's messages, attachments and the
  last confirmation question from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard, receipt and hook tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/claims.py`. The model supplies a policy number, a
  loss type, a date, the customer's account, file names to leave out, a
  reference and a reason, never a fact or an attachment state.
- Attachment states come from the attachment service, never from the model or
  the customer saying they sent something. Files are read from the customer's
  messages: `[attached: ...]` markers in web chat, `metadata.attachments` on
  Teams.
- `submit_claim_report` is hidden from the model until every required
  attachment state is known (`requires` on `claim_ready_to_submit`), has an
  engine confirmation gate that reads the draft back with its version tag, and
  checks that tag itself. It sets no `utter_on_user_denial`, so a correction at
  the confirmation is answered in the same turn.
- A claim is filed only when the claims system acknowledges it. A receipt
  lists material received and still needed; `coverage_decision` is always
  `None`.
- `TOOL_SENDS_RECEIPT = True` in `lib/claims.py`: the tools send the claim
  reference to the customer through `ToolContext.send`. Keep it on; the
  `receipt-in-result-only` variant shows what happens without it.
- Each memory value is one short field under 100 characters. Mantle cuts
  longer values in the prompt without a log line; `tests/test_guard.py`
  checks every fixture combination.
- The fixture's organisation fields must be the casebook contract's own
  fictional insurer, marked `(fictional ...)`; the library refuses to load
  otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
