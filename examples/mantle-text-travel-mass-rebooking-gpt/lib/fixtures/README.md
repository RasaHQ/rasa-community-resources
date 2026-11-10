# Fixture data (entirely fictional)

Horizon Travel, the storm, its flights, the passengers Noor Castellan and
Teodor Brandt, their disruption cases, the holds and every reference here are
invented for this project. Airport codes are used only as places. Nothing
here corresponds to a real airline, travel company, person or booking. Do not
replace these records with real passenger data; this catalog is public.
`lib/rebooking.py` refuses at import any fixture whose organisation fields
are not the casebook contract's own fictional company (an allowlist) marked
`(fictional ...)`.

- `horizon_disruption.json`: the synthetic cases, recovery inventory, holds
  and booking-service outcomes. `as_of` is the fixture clock; it moves
  `minutes_per_passenger_message` (6) for every passenger message, so hold
  expiry is deterministic. Three outcomes are scripted faults:
  - `RB-1301` (HZ 216) shows one seat in search, and another passenger's hold
    takes it before this passenger's hold (the case's failure);
  - `RB-1305` (HZ 118) holds for 5 minutes, so a hold made in one message has
    expired when the passenger answers the confirmation in the next (the
    case's recovery);
  - `RB-1306` (HZ 350) is taken by the booking service but not ticketed, so a
    commit comes back pending (the receipt rule).
  `RB-1304` (HZ 220) arrives after the onward Funchal flight, and `RB-1302`
  (HZ 318) has a stair-and-bus connection, so neither meets every
  constraint. `HT-RH-7710` is a hold made in the app that expired this
  morning.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/travel-mass-rebooking.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import; a `data/` folder is not packaged.
