# Fixture data (entirely fictional)

HarborCover, its policyholders Maria Delgado, James Whitfield, Priya Raman and
Kevin O'Hara, their policies, vehicles and addresses, the roadside providers
(Ridgeline Towing, Easton Flatbed Services, Harbor Hook and Flatbed,
Grayhaven Heavy Recovery, Millbrook Road Help, Quarry Hill Auto, Coastline
Roadside), the towns, roads and places, and every reference are invented for
this project. Do not replace these records with real data; this catalog is
public. `lib/roadside.py` refuses to load a fixture whose insurer is not the
organisation the casebook contract names, marked fictional, or whose
providers are not on the fixture's own list of fictional providers.

- `harborcover_roadside.json`: the synthetic policies, places and providers.
  Coordinates are kilometres on an invented map, used only to rank providers
  by distance. What each provider answers to a job is fixture data
  (`answers`), since the build has no providers:
  - Ridgeline Towing has only a wheel-lift truck: fine for a two-wheel-drive
    pickup, wrong for an all-wheel-drive electric car or a heavy van.
  - Harbor Hook and Flatbed declines every job (no truck free): the recovery
    rule.
  - Quarry Hill Auto has not answered when the job is sent and accepts on
    the first check: acceptance is not yet known.
  - Coastline Roadside accepts without giving an arrival time.
  - No heavy-duty tow covers Easton Falls.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/insurance-roadside.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
