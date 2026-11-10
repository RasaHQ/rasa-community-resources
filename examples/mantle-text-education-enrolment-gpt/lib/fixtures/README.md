# Fixture data (entirely fictional)

Pine University, Rowan Ashby, Tamsin Coyle, the applications, teams, dates and
references are invented for this project. Nothing here corresponds to a real
university, applicant, application or award. Do not replace these records
with real data; this catalog is public. `lib/enrolment.py` refuses to load a
fixture whose organisation fields are not the casebook contract's own
fictional university (an allowlist) marked `(fictional ...)`.

- `pine_records.json`: the synthetic applicant records and team queues.
  `as_of` is the fixture clock. `session_applicant_id` is the signed-in
  applicant the web chat is bound to. Each record lists the stage every
  source reports (`sources`); when two sources disagree, as the applicant
  portal and the scholarships committee do for `SCH-26-0309`, no stage can be
  given. `decision` is `null` unless the team issued one; the only issued
  decision is the admission offer on `ADM-26-4471`. `deadlines` carry the
  authoritative source each date comes from. `AID-25-0931` sits on a duplicate
  applicant record that is being merged (`merge_pending_with`), and
  `AID-26-1190` belongs to another applicant. A team's `queue` sets how its
  synthetic case queue answers: `ok`, or `ack_lost` (it records the enquiry
  but the acknowledgment is lost). `existing_enquiries` holds enquiries
  recorded before the session.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/education-enrolment.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
