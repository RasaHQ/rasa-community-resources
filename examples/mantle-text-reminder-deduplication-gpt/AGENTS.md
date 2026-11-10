# Rasa Skills project: Cedar Clinic appointment reminders (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`reminder-deduplication`. Cedar Clinic is a fictional clinic. The case's
target channel is Twilio SMS; the build runs in web chat until the programme
has a Twilio account.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`
(the `twilio` block to add is in `integrations.yml`).

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_patient_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `appointment_reminders`
- `skills/appointment_reminders/tools.py`: `send_appointment_reminder`,
  `record_reminder_reply`, `request_appointment_change`
- `tools/cedar_reminders.py`: `load_patient_profile`, `list_appointments`,
  `check_reminder_delivery`
- `lib/reminders.py`: bookings with revisions, the reminder ledger, the text
  gateway, the case guard, the patient's reply, receipts and the sent-claim
  words, no Rasa imports
- `lib/conversation.py`: the patient's messages and the reminders sent, from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- A reminder's identity is its appointment revision (`reminder_ref`). The
  tools read the current revision from the booking system at queueing and
  again at delivery; the model never supplies a revision, a time the tools
  trust, a fact, a patient id or an attendance answer.
- Delivery and attendance stay separate. Only `record_reminder_reply`, reading
  the patient's own message, records attendance, and only for the current
  revision.
- Reminders go only to the confirmed SMS number on file.
- Memory values are written only by the tools, one short field per value under
  100 characters; `tests/test_guard.py` checks every value the fixture allows.
  Appointment times are never kept in project memory (write-once).
- Any regex over bot text reads straight and typographic apostrophes (GPT-5.5
  writes `’`). Keep the `sent_claim` metric in
  `case-build/conversations.json` identical to `lib/reminders.py`; the tests
  check it.
- `lib/reminders.py` refuses fixtures whose organisation is not the casebook's
  fictional clinic (an allowlist, not a list of real names).
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
