# Fixture data (entirely fictional)

HarborCover, Delphine Marsh, Callum Frye, the policies, addresses, files and
references are invented for this project. Nothing here corresponds to a real
insurer, policyholder, property or claim. Do not replace these records with
real data; this catalog is public. `lib/claims.py` refuses to load a fixture
whose organisation fields are not the casebook contract's own fictional
insurer (an allowlist) marked `(fictional ...)`.

- `harborcover_claims.json`: the synthetic policies and services. `as_of` is
  the fixture clock that dates of loss are checked against, so results do not
  depend on the day you run them. `intake_service` sets how the synthetic
  claims system answers for a policy: `ok`, `ack_lost` (it records the
  submission but the acknowledgment is lost) or `unavailable` (nothing can be
  confirmed). `uploads` is the synthetic attachment service: the state of
  each file a customer can attach, as a list that advances with each customer
  message after the one that attached it (`processing` then `received` is a
  virus scan finishing; `processing` alone never finishes during the chat).
  `existing_claims` holds a claim filed before the session.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/insurance-file-claim.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
