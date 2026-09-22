---
name: Check Balance
description: Look up an account balance.
import_tools:
  - list_accounts
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
---

Help the customer check a balance. Do not invent balances.

if: not session.check_balance.account_number
Call list_accounts and ask which account.

if: session.check_balance.account_number
Call check_balance and read the amount aloud.
