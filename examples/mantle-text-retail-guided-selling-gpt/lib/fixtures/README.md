# Fixture data (entirely fictional)

Willow Shop, its catalogue, the Lumen devices, the spec-sheet and fit-test ids
and the stock counts are invented for this project. Nothing here corresponds
to a real retailer, manufacturer, product or customer. Do not replace these
records with real catalogue data; this catalog is public.

- `willowshop.json`: the synthetic catalogue. Each product attribute has a
  `value` and a `source` (a spec sheet or a Willow Shop fit test); a `null`
  source means the catalogue does not know. `description` is marketing prose
  and is never read as evidence. `as_of` is the fixture clock that stock
  freshness is measured against, so results do not depend on the day you run
  them.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/retail-guided-selling.json`, the
  lab contract whose three request-phase rules the tools enforce.
  `tests/test_guard.py` fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
