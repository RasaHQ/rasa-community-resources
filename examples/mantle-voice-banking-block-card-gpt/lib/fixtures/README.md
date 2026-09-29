# Fixture data (entirely fictional)

Northgate Bank, its customers Nadia and Marcus Okafor, and their cards are
invented for this project. The card endings are four digits only; there are
no card numbers. Do not replace these records with real data; this catalog is
public.

- `northgate.json`: the synthetic card service. Nadia has five cards: two
  debit cards (so "my debit card" is ambiguous), a debit and a credit card
  that share the ending 5502 (so the ending alone is ambiguous), and a prepaid
  card whose state the service cannot read back (`read_back: unavailable`),
  which exercises the receipt rule. Marcus's card is someone else's card for
  every call Nadia makes.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-block-card.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails if
  the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
