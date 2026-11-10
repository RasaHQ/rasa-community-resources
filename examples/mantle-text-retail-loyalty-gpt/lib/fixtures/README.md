# Fixture data (entirely fictional)

Willow Shop, its members, subscriptions, prices, dates, entitlements and
loyalty points are invented for this project. Nothing here corresponds to a
real retailer, person or account. Do not replace these records with real
customer data; this catalog is public.

- `willow_shop_subscriptions.json`: the synthetic subscription service. `as_of`
  is the fixture clock, so results do not depend on the day you run them.
  Each subscription lists what the service computes for each of the three
  changes (`stop_renewal`, `pause`, `cancel_now`): the effective time, a
  one-line entitlement summary read back in the confirmation question, and
  what the member keeps. Two subscriptions carry a fault:
  - `WS-SUB-3303` (Pet Pantry autoship) has `command_response:
    timeout_then_applied`: the first command's answer is lost, though the
    service applied it. Only a status read by request key recovers it.
  - `WS-SUB-3304` (Style Box) has `update_on_first_command`: the October box
    is charged while the chat is open, so the subscription moves to revision
    5 and every option's effect changes before the first command runs.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/retail-loyalty.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

`lib/subscriptions.py` refuses to load a fixture whose organisation is
anything but the contract's own fictional retailer, marked fictional. These
files live under `lib/` because Mantle packages `lib/` into the model snapshot
and the tools read them at runtime; a `data/` folder is not packaged.
