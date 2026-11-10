# Fixture data (entirely fictional)

Willow Shop, the carrier Larkspur Parcel, the customers Dana Whitlock and
Rafael Ostrander, their orders, items, depots and every timestamp are
invented for this project. Do not replace these records with real data; this
catalog is public. `lib/orders.py` refuses to load a fixture whose retailer
or carrier is not marked fictional or names a real retailer or carrier.

- `orders.json`: the synthetic order-tracking service, on a fixed clock
  (`as_of`, 2026-09-30 12:00 US Eastern) with a 6-hour carrier freshness
  window. Dana, the signed-in customer, has five orders, each built to break
  one part of the case open:
  - `WS-10482`: delivered, with a full carrier trail.
  - `WS-10517`: only a warehouse shipping label, current carrier feed, no
    carrier scan, and a checkout estimate. The case's failure lives here.
  - `WS-10539`: split into two parcels. Parcel 1 was delivered, parcel 2 is
    in transit with a carrier estimate. Asking about "the order" without a
    parcel is ambiguous.
  - `WS-10560`: the carrier feed was last observed about 66 hours before the
    fixture clock: stale.
  - `WS-10571`: the only record is a legacy warehouse-feed `SHIPPED` with no
    milestone type.
  - `WS-10493` belongs to Rafael: someone else's order for every call Dana
    makes.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/retail-order-status.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
