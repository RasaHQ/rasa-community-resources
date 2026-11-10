# Fixture data (entirely fictional)

Amber Grid, its customers, accounts, balances and payment-plan offers are
invented for this project. Nothing here corresponds to a real energy supplier,
person or account. Do not replace these records with real customer data; this
catalog is public.

- `amber_grid_billing.json`: the synthetic billing service. `as_of` is the
  fixture clock that offer expiry is measured against, so results do not
  depend on the day you run them. `offers` holds every offer the billing
  service knows, including one it never authorized (`AG-OFR-4471-C`, terms a
  customer asked for). `refresh` says what the billing service does when an
  account's offers are refreshed: `unchanged`, `reissued` (a new revision with
  new terms) or `no_eligible_offer`.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/payment-plan-authority.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

`lib/plans.py` refuses to load a fixture whose organisation is anything but
the contract's own fictional supplier, marked fictional. These files live
under `lib/` because Mantle packages `lib/` into the model snapshot and the
tools read them at runtime; a `data/` folder is not packaged.
