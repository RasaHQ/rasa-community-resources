# Fixture data (entirely fictional)

Horizon Travel, its Horizon Rewards programme, the partner airline Atlantic
Coast Air, the members, accounts, flights, hotels, holds and redemptions are
invented for this project. Nothing here corresponds to a real airline, hotel,
loyalty programme, person or booking. Do not replace these records with real
member data; this catalog is public.

- `horizon.json`: the synthetic points ledger, reward inventory and booking
  outcomes. `as_of` is the fixture clock. It does not move during a
  conversation, so a hold made in chat never expires mid-test; the one expired
  hold (`HT-H-7710`) is recorded that way in the data. Two outcomes are
  scripted faults: `RW-LIS-1019` loses its last seat between search and hold,
  and `RW-OPO-3302`'s partner rejects ticketing after the points are debited.
  `HT-RD-58213` is an earlier redemption that already ended that way.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/travel-redemption.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import; a `data/` folder is not packaged.
