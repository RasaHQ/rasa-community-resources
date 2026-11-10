# Fixture data (entirely fictional)

Amber Grid, its customers, premises, service points and move orders are
invented for this project. Nothing here corresponds to a real energy supplier,
person, address or account. Do not replace these records with real customer
data; this catalog is public.

- `amber_grid_moves.json`: the synthetic premises register, service points
  and move-order system. `as_of` is the fixture clock that dates are measured
  against, so results do not depend on the day you run them; `window_days` is
  how far ahead a move can be scheduled in chat. Each premises says how the
  move-order system behaves for an order to it: `acknowledges`,
  `loses_acknowledgment` (the order is committed but the acknowledgment never
  arrives), `never_confirms`, or `reads_back_closure_a_day_early` (the order
  system stores the move-out as the start of that day). `41 Quarry Lane` has
  six flats and `22 Orchard Rise` exists in two towns, so neither resolves
  from the street alone. `3 Heron Wharf` is a new build with no supply point.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/utilities-service-move.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

`lib/moves.py` refuses to load a fixture whose organisation is anything but
the contract's own fictional supplier, marked fictional. These files live
under `lib/` because Mantle packages `lib/` into the model snapshot and the
tools read them at runtime; a `data/` folder is not packaged.
