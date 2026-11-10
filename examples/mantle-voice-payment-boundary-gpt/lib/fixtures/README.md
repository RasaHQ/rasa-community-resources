# Fixture data (entirely fictional)

Willow Shop, the payment processor Quillfeather Payments, the customers Dana
Whitlock and Rafael Ostrander, their orders, phone numbers (555-01xx) and
example.com email addresses are invented for this project. The card numbers
the scripted callers read out are the card networks' published test numbers,
which no bank issues. Do not replace these records with real data; this
catalog is public. `lib/payments.py` refuses to load a fixture whose
organisation is not exactly the casebook contract's organisation marked
`(fictional)`, whose processor is not marked fictional, or whose customer
contacts are outside the reserved ranges. It keeps no list of real names: the
check is an allowlist.

- `orders.json`: Dana's orders, each built to exercise one part of the case:
  - `WS-10517` oak entryway bench, 149 dollars, and `WS-10528` brass table
    lamp, 62 dollars 50: the processor captures the payment and signs a
    receipt that verifies.
  - `WS-10546` wool area rug, 89 dollars 99: the first link expires unpaid; a
    second one is paid.
  - `WS-10563` walnut bookshelf, 210 dollars: the processor reports a capture,
    but its receipt signature does not verify, so the payment stays pending.
  - `WS-10581` patio chairs from a partner seller: no hosted payment session
    can be opened, so collection is cancelled and the caller gets the approved
    alternative.
  - `WS-10592` throw pillows: paid in full, nothing owed.
  - `WS-10610` belongs to Rafael, not the signed-in customer.

  The simulated processor reports a session's outcome from the caller turn
  after the link went out: a caller pays on their phone between turns. The
  receipt signing key is a fixture value, not a secret.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/voice-payment-boundary.json`,
  the lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
