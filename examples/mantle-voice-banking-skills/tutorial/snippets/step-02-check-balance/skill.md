---
name: Check Balance
description: >
  Look up the balance on one of the customer's bank accounts. Activate when the
  customer asks about balance, available funds, or how much money is in an account.
import_tools:
  - load_customer_profile
  - list_accounts
  - check_balance
---

Help the customer check an account balance. Do not invent balances.

If username is missing in project memory, call `load_customer_profile`.

Call `list_accounts` if you do not know which account they mean.
Ask for the account number, then call `check_balance`.
Report the balance clearly in spoken language.
