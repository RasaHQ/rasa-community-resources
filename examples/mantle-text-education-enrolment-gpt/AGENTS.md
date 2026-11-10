# Rasa Skills project: Pine University applicant support (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`education-enrolment`. Pine University is a fictional university.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`
(the matrix channel is web chat).

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_applicant_profile` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in applicant, then greets
- `skills/application_enquiry/`: the skill, `lookup_application` and the
  gated `record_enquiry`, the contract's confirmation question and the record
  memory the lookup writes
- `skills/enquiry_status/`: status of an enquiry already recorded
- `tools/pine_applicant.py`: `load_applicant_profile`, `check_enquiry`,
  `route_to_team`
- `lib/enrolment.py`: records, team queues, the case guard, the organisation
  allowlist, receipts and the word patterns, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against describing a received form as an
  admission or an award, or promising an extension
- `tests/`: offline guard, receipt, word and hook tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/enrolment.py`. The model supplies a reference or the
  applicant's words for a form, a topic, the applicant's question and a
  reason; never a fact, an applicant id, a stage, a decision or a deadline.
  `tests/test_guard.py` fails if a tool gains a parameter that could carry one.
- `record_enquiry` is hidden until `lookup_application` has resolved a record
  (`requires` on `enquiry_ref`), sits behind the engine's confirmation with
  the contract's question, and checks that its reference is the one the
  question named. It sets no `utter_on_user_denial`, so a correction given in
  answer to the question is answered in the same turn.
- A received or submitted form is never a decision. `decision` is `null`
  unless the team issued one; the only issued decision in the fixture is the
  admission offer on `ADM-26-4471`. When sources disagree there is no stage
  and no decision, and the case is routed.
- Deadlines come from the authoritative source named with each one. No tool
  takes or changes a deadline.
- `TOOL_SENDS_RECEIPT = True` in `lib/enrolment.py`: the tools send the
  support or desk reference through `ToolContext.send`, once per reference.
  Keep it on; the `receipt-in-result-only` variant shows what happens
  without it.
- Every word pattern matches straight and typographic apostrophes; GPT-5.5
  writes "can’t" with U+2019. The spec's `bot_text_metrics` are copies of the
  library patterns and a test keeps them identical.
- Each memory value is one short field under 100 characters. Mantle cuts
  longer values in the prompt without a log line; `tests/test_guard.py`
  checks every record.
- The fixture's organisation fields must be the casebook contract's own
  fictional university, marked `(fictional ...)`; the library refuses to load
  otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
