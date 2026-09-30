# Fixture data (entirely fictional)

Northgate Bank, Elena Marsh, Jordan Vale, the accounts, merchants, amounts,
statements and references are invented for this project. Nothing here
corresponds to a real bank, customer, merchant or transaction. Do not replace
these records with real data; this catalog is public. `lib/history.py` refuses
to load a fixture whose organisation fields are not the casebook contract's
own fictional bank (an allowlist) marked `(fictional ...)`.

- `northgate_history.json`: the synthetic transaction history and statements.
  `as_of` (2 April 2026, 15:00 Eastern) is the fixture clock that periods are
  resolved against, so results do not depend on the day you run them.
  Timestamps are UTC; a search filters on the date in `timezone`. Some rows
  carry a `fixture_note` saying which trap they set: a pending Acme Hardware
  charge on 1 April (the case's failure), a pending charge at 21:45 on
  31 March that is already 1 April in UTC, and a coffee on 28 February at
  23:30 that is 1 March in UTC. `history_source` sets how the synthetic
  history service pages: 10 rows a page, 3 pages a request, the archive
  (before 1 April 2025) one page a request, and the Rewards Card's second
  page cut short the first time it is asked. `statements` hold each
  account's billing cycles; the checking and card cycles are not calendar
  months.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-statement-search.json`,
  the lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import. The generator is not shipped;
the JSON is the source of truth.
