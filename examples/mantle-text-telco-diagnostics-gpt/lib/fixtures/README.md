# Fixture data (entirely fictional)

Juniper Mobile, its customers, addresses, exchange areas, incidents and
devices are invented for this project. Nothing here corresponds to a real
operator, person, place or network. Do not replace these records with real
customer data; this catalog is public.

- `juniper.json`: the synthetic network, outage and device services. `as_of`
  is the fixture clock. Area `MB-04` has an active outage, `EV-11` is clear,
  and `LA-02`'s outage feed is unavailable, so its status is unknown.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/telco-diagnostics.json`, the lab
  contract whose three request-phase rules the tools enforce.
  `tests/test_guard.py` fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at runtime; a `data/` folder is not packaged.
