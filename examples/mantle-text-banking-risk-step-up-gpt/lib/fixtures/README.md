# Fixture data (entirely fictional)

Northgate Bank, its customers, accounts, payees, assessments and verifications
are invented for this project. Nothing here corresponds to a real bank, person
or account. Do not replace these records with real customer data; this catalog
is public.

- `northgate.json`: the synthetic payments and identity-risk service.
  - `as_of` is the fixture clock every rule is evaluated against, fixed for
    every conversation, so results do not depend on the day you run them.
  - `prior_assessments` and `prior_verifications` are two transfers the
    customer started earlier that day and never sent: one assessed before the
    payee's bank details changed, one verified with a code that has lapsed.
  - `demo_codes` are the codes the fictional registered phone receives, in
    order, one per step-up in a conversation (a resend repeats the same code).
    Tools never return a code; the scripted customer types it.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-risk-step-up.json`, the lab
  contract whose three request-phase rules the tools enforce.
  `tests/test_guard.py` fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at runtime; a `data/` folder is not packaged.
