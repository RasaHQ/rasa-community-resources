---
name: Transfer Money
description: >
  Send money from the caller's account to one of their existing payees.
  Activate for send money, pay someone, or make a transfer.
import_tools:
  - get_customer_info
tool_constraints:
  - make_transfer:
      requires: session.transfer_money.transfer_confirmed
---

Move money for the caller.

Collect, one at a time: who the money is going to, and how much. Never ask for
a reason — only record one if the caller volunteers it unprompted.

Read the details back and ask them to confirm. Only when they confirm, set
`transfer_confirmed` to true with `set_fields`, then call `make_transfer`.

`make_transfer` reads the signed-in customer from project memory. If it returns
`not_authenticated`, tell the caller you need to verify them first and let the
Authenticate skill run. If it returns `payee_not_found`, read back the payees it
lists and ask which one they meant.

When it succeeds, confirm briefly. You may call `get_customer_info` to greet
them by name — the same shared tool the Check Balance skill imports.
