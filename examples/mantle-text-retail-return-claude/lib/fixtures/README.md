# Fixture data (entirely fictional)

Willow Shop, Larkspur Parcel, Imogen Faraday, Theo Brandt, the orders, items,
SKUs, stock counts and references are invented for this project. Nothing here
corresponds to a real retailer, carrier, product or customer. Do not replace
these records with real data; this catalog is public. `lib/returns.py` refuses
to load a fixture whose retailer or carrier is not marked `(fictional ...)` or
names a real brand.

- `returns.json`: the synthetic orders. `as_of` is the fixture clock that the
  30-day return window and stock freshness are measured against, so results do
  not depend on the day you run them. `returns_service` sets how the synthetic
  returns service answers for an item: `ok`, `ack_lost` (it records the
  authorization but the response is lost) or `unavailable` (nothing can be
  confirmed). `existing_return` is a return authorized before the session.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/retail-return.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
