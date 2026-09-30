# Fixture data (entirely fictional)

Orchard Works, Marisol Quint, Dev Harlow, Tomasz Rell, the internal systems,
roles, approvals, tickets and references are invented for this project.
Nothing here corresponds to a real company, product or person. Do not
replace these records with real data; this catalog is public.
`lib/helpdesk.py` refuses to load a fixture unless its organisation is
exactly the casebook contract's (`Orchard Works`), marked `(fictional)`,
every system carries that name, and every email address is on the reserved
`orchard.example` domain. That is an allowlist; the repository lint keeps
the list of real names.

- `orchard_access.json`: the synthetic directory. `session_employee` is the
  employee signed in to the chat. `as_of` is the fixture clock that approval
  expiry is measured against, so results do not depend on the day you run
  them. Each role's `owner` is the only approver for it; `directory` sets how
  the synthetic directory answers the read-back after a change: `ok`,
  `ack_lost` (the change is made but the first read-back fails) or
  `unavailable` (nothing can be confirmed). `approvals` holds owner
  approvals, one expired approval and one line-manager endorsement, which
  is not an approval. `tickets` holds one ticket opened before the session.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/internal-it-helpdesk.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
