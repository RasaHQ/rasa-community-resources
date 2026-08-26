---
name: Check Balance
description: >
  Look up the balance on one of the customer's bank accounts. Activate when the
  customer asks about balance, available funds, or how much money is in an account.
import_tools:
  - load_customer_profile
  - list_accounts
  - check_balance
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
---

Help the customer check an account balance. Do not invent balances.

If username is missing in project memory, call `load_customer_profile`.

if: not session.check_balance.account_number
Call `list_accounts` and present the accounts (type and account number).
Ask which account they want. When they choose, set `account_number` via
`set_fields` to the matching account number. If they already gave a clear
account number, set it without re-asking.

if: session.check_balance.account_number
Call `check_balance` and report the balance clearly in spoken language
(for example: "Your current account ending in 6789 has four thousand nine
hundred twenty-three dollars and sixty-seven cents").
