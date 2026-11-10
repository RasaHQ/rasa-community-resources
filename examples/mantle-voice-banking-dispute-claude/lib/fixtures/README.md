# Fixture data (entirely fictional)

Northgate Bank, its customers Priya and Arjun Raghunathan, their cards, the
merchants and every transaction are invented for this project. Card endings
are four digits only; there are no card numbers. Amounts are in rupees. Do
not replace these records with real data; this catalog is public.

- `northgate_disputes.json`: the synthetic card ledger and dispute case
  service. Priya has two Lakeview Fuel charges (so "the Lakeview Fuel
  charge" is ambiguous), a Hollins Fitness membership she will recognise
  once it is read back, a Saffron Table charge whose filing acknowledgement
  is lost (`case_service: ack_lost`: the case is recorded, the read-back
  fails, and a lookup by submission key finds it), and a Metro Cabs charge
  the case service cannot confirm at all (`case_service: unavailable`).
  Arjun's Brightmart Online charge is someone else's transaction for every
  call Priya makes.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-dispute.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
