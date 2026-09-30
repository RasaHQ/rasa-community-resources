# Fixture data (entirely fictional)

Cedar Clinic, the patient Nadia Farrow, Larchmere Health Plan, Oakhollow
Mutual Health, the member ids, phone numbers and references are invented for
this project. Nothing here corresponds to a real clinic, payer, patient or
insurance plan. Do not replace these records with real data; this catalog is
public. `lib/intake.py` refuses to load a fixture whose organisation is not
the casebook contract's own fictional clinic, or whose other organisation
fields are not one of the two invented payers it allowlists, each marked
`(fictional ...)`.

- `cedar_intake.json`: the synthetic registration record, visit, payer
  directory and eligibility service. `as_of` is the fixture clock.
  `eligibility` maps a payer and member id to one of the build's own response
  codes (`lib/intake.py`, `RESPONSE_CODES`): `EL-1` active coverage, `EL-6`
  coverage inactive, `EL-42` payer unable to respond. Any other member id of
  a listed payer returns `EL-75` member not found, and a payer that is not in
  the directory returns `EL-NP`, no electronic check. The codes are this
  build's, not a standard's.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/healthcare-intake.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
