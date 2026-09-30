# Fixture data (entirely fictional)

Juniper Mobile, its customers, accounts, services, offers, campaigns and
references are invented for this project. Nothing here corresponds to a real
mobile or broadband provider, person, address or account. Do not replace
these records with real customer data; this catalog is public.

- `juniper_retention.json`: the synthetic accounts, services, offer catalogue
  and campaign dispatch. `as_of` is the fixture clock that offer validity is
  measured against, so results do not depend on the day you run them.
  - The **mobile ending 4471** has one authorized offer (`JM-OFR-M12`), one
    that expired on 15 September (`JM-OFR-M24`) and one draft that was never
    authorized (`JM-OFR-WB60`, "60% off").
  - The **home fibre** account's retention-contact record says withdrawn on
    14 August, but its campaign dispatch never acknowledges a withdrawal, so
    the win-back campaign still lists it: the permission records disagree.
  - The **tablet data SIM**'s cancellation route points to the retention
    sales queue instead of the cancellations desk: its exit is blocked.
  - `JM-FIB-204420` at 5 Tanner Close belongs to another customer.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/telco-retention.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails
  if the two copies drift apart.

`lib/retention.py` refuses to load a fixture whose organisation is anything
but the contract's own fictional provider, marked fictional. These files live
under `lib/` because Mantle packages `lib/` into the model snapshot and the
tools read them at runtime; a `data/` folder is not packaged.
