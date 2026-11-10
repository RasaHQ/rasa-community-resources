# Fixture data (entirely fictional)

Horizon Travel, its partners Horizon Transfers, Horizon Park and Fly, and
Sierra Walks, the travellers Ines Calloway and Marcus Oyelaran, their
bookings, flights, references, phone numbers (555-01xx) and example.com email
addresses are invented for this project. Airport codes and city names are
used only as places. Do not replace these records with real data; this
catalog is public. `lib/journeys.py` refuses to load a fixture whose
organisation is not exactly the casebook contract's organisation marked
`(fictional)`, whose partners are not marked fictional, whose service
providers are not among those partners, or whose traveller contacts are
outside the reserved ranges. It keeps no list of real names: the check is an
allowlist.

- `journeys.json`: the booking clock is the evening of October 23, 2026.
  Ines's bookings, each built to exercise one part of the case:
  - `HZ4R8N`, Denver to Lisbon and back through Boston. The outbound flights
    (`HZ 431`, `HZ 214`, October 16) are flown. The return is `HZ 215`
    Lisbon to Boston on October 24, connecting to `HZ 438` Boston to Denver,
    with a hotel pickup in Lisbon, a checked bag tagged through to Denver and
    Denver airport parking that must be exited by 11:59 PM on October 24.
    - Moving `HZ 215` to `HZ 219` the same afternoon moves the connection to
      `HZ 442`, moves the pickup and re-tags the bag; the parking still
      covers the new arrival. Every service reconciles.
    - Moving it to October 25 moves the connection, pickup and bag, but the
      parking partner does not extend automatically: a partial change, so
      the booking is frozen for the travel desk.
    - Moving only `HZ 438` checks the Lisbon flight before it, re-tags the bag
      and checks the parking (same day: complete; next day: partial).
    - `HZ 215` on October 24 is running 40 minutes late. The connection still
      works, and the delay changes nothing on the booking.
  - `HZ6P2L`, Boston to Dublin and back in November, with a coach to Galway
    after the outbound flight and a coach back to Dublin Airport before the
    return: both flights can move a day, and each coach moves with its
    flight. It is the correction's two-leg trip.
  - `HZ3M9V`, Boston to Madrid, with a walking-tour pickup from a partner
    whose status cannot be read: the dependent-services check fails and
    nothing changes.
  - `HZ8D1X` belongs to Marcus, not the signed-in traveller.

  Each segment's replacement flights are listed under `options`; a connecting
  flight is moved to the first option that leaves at least its minimum
  connection time after the new arrival.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/travel-booking.json`, the lab
  contract whose three rules the tools enforce. `tests/test_journeys.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
