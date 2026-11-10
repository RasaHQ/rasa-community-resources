# Fixture data (entirely fictional)

Orchard Works, its employees Tara Brennan, Daniel Frost, Owen Mercer, Rachel
Collins, Samir Haddad and Grace Porter, their employee numbers, phones and
every reference are invented for this project. Do not replace these records
with real data; this catalog is public. `lib/access.py` refuses to load a
fixture whose organisation is not marked fictional or is not the organisation
the casebook contract names.

- `orchard_directory.json`: the synthetic directory and verification service.
  Each employee's `approval` says how the prompt on their registered phone is
  answered, since the build has no phones:
  - Tara Brennan and Daniel Frost approve: genuine callers.
  - Owen Mercer, a vice president, denies: his is the familiar name an
    impostor uses, and the real Owen asked for nothing.
  - Rachel Collins never answers, so her challenge times out (the recovery
    rule).
  - Samir Haddad is on leave and never answers: a manager asks for his
    access.
  - Grace Porter approves late: the first check is still waiting.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/step-up-authentication.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
