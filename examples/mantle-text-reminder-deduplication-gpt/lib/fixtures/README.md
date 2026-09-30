# Fixture data (entirely fictional)

Cedar Clinic, its patients, clinicians, sites, phone numbers, appointments and
reminder references are invented for this project. Nothing here corresponds to
a real clinic, person, number or booking. Do not replace these records with
real patient data; this catalog is public. Not medical guidance.

- `cedar_reminders.json`: the synthetic booking system, reminder ledger and
  contacts. `as_of` is the fixture clock, so results do not depend on the day
  you run them. Each appointment keeps every revision of its booking; the last
  one is current. `delivery` says how the text gateway behaves for a reminder
  about that appointment: `delivers`, `loses_acknowledgment` (the text reaches
  the phone but the acknowledgment never comes back), `fails_first_attempt`
  (the carrier rejects the first text), or `rescheduled_before_delivery` (the
  front desk moves the appointment between queueing and delivery, the case's
  evidence scenario). The ledger starts with a delivered reminder for the
  follow-up's first version (moved since), a delivered reminder for the
  physiotherapy session, and a queued one for the blood test. `CC-APT-9150`
  belongs to another patient.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/reminder-deduplication.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

`lib/reminders.py` refuses to load a fixture whose organisation is anything
but the contract's own fictional clinic, marked fictional. These files live
under `lib/` because Mantle packages `lib/` into the model snapshot and the
tools read them at runtime; a `data/` folder is not packaged.
