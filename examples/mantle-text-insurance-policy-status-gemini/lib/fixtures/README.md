# Fixture data (entirely fictional)

HarborCover, its customers, policies, claims and decisions are invented for
this project. Nothing here corresponds to a real insurer, person or claim.
Do not replace these records with real customer data; this catalog is public.

- `harborcover.json`: the synthetic status service. `as_of` is the fixture
  clock that freshness is measured against, so results do not depend on the
  day you run them.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/insurance-policy-status.json`, the
  lab contract whose three request-phase rules the tools enforce.
  `tests/test_guard.py` fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at runtime; a `data/` folder is not packaged.
