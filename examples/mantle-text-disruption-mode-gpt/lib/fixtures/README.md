# Fixture data (entirely fictional)

Horizon Travel, Ines Calloway, Tomas Rheinfeld, the bookings, flights, holds,
queue and the storm incident are invented for this project. Nothing here
corresponds to a real airline, passenger or journey. Do not replace these
records with real data; this catalog is public. `lib/recovery.py` refuses to
load a fixture whose organisation fields are not the casebook contract's own
fictional organisation (an allowlist) marked `(fictional ...)`.

- `horizon_disruption.json`: the synthetic disruption services.
  - `now` is the fixture clock. Hold expiries and the state of existing holds
    are computed from it, so results do not depend on the day you run them.
  - `incident` is the storm incident. It starts at revision 4 and moves to
    revision 5 right after the first search for the Denver booking in a
    conversation, which cancels the Denver option that search listed.
  - `options` are the recovery flights per booking and revision.
    `seats_shown` is what a search displays; `inventory` is what the hold
    service can actually hold. They differ for HZ 319 to Chicago: the count
    shown lags the inventory.
  - `hold_service` marks a route whose holds cannot be confirmed (Washington).
  - `bookings.*.ticketed_by: partner` is a ticket issued by a partner
    airline, which has no recovery channel in this chat (Toronto).
  - `existing_holds` were placed in the app before the chat: one active
    (Miami), one expired (Chicago), and one on another passenger's booking.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/disruption-mode.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
