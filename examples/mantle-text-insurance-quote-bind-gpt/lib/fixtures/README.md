# Fixture data (entirely fictional)

HarborCover, its customers, addresses, vehicles, quotes, offers and prices are
invented for this project. Nothing here corresponds to a real insurer, person
or policy. Do not replace these records with real customer data; this catalog
is public.

- `harborcover_quotes.json`: the synthetic quote, underwriting and binding
  services. `as_of` is the fixture clock that offer expiry is measured against,
  so results do not depend on the day you run them. `binding_service` sets
  what the binding service does for a quote: `confirms` (a matching receipt),
  `no_receipt` (accepts the request and returns nothing) or
  `mismatched_receipt` (a receipt for other answers; unit tests only).
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/insurance-quote-bind.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at runtime; a `data/` folder is not packaged.
