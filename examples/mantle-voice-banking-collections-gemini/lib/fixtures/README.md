# Fixture data (entirely fictional)

Northgate Bank, its hardship teams, the customers Marisol Quintero and
Esteban Ruvalcaba, the collections officer Ofelia Barragan, every account,
amount, offer and date are invented for this project. Do not replace these
records with real data; this catalog is public. `lib/repayment.py` refuses to
load a fixture whose organisation is not exactly the casebook contract's
fictional organisation, `Northgate Bank (fictional)`.

- `accounts.json`: the synthetic collections service, on a fixed clock
  (`as_of`, 2026-09-30 12:00 US Eastern). Marisol, the signed-in customer, has
  two past-due accounts, each built to break one part of the case open:
  - card `4471`: 612 dollars past due. Two current offers (three payments of
    204 dollars, six of 102, first due 15 October) and one expired offer
    from an August letter (four payments of 153 dollars, terms version
    2026-08-20, valid until 15 September). The letter's plan is the stale
    terms the guard refuses.
  - loan `0938`: 310 dollars past due, one current offer, but the loan
    hardship team's referral queue is down (`hardship_routes.loan.available:
    false`). With no hardship exit, automated plans are off for the loan and
    a hardship request is preserved with a human callback.
  - card `6603` belongs to Esteban: someone else's account for every call
    Marisol makes.
  Account labels spell the last four digits in words ("cuatro cuatro siete
  uno"), because the agent's Rime voice reads "4471" as one number.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-collections.json`, the lab
  contract whose three rules the tools enforce. `tests/test_guard.py` fails
  if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
