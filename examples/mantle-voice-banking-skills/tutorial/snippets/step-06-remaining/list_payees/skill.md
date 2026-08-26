---
name: List Payees
description: >
  List the customer's authorised payees. Activate when they ask who they can
  pay, which payees they have, or to show transfer recipients.
import_tools:
  - load_customer_profile
  - get_payees
---

Help the customer review authorised payees.

If username is missing, call `load_customer_profile`.
Call `get_payees` and read the names clearly.
Offer to add a payee, remove a payee, or start a transfer.
