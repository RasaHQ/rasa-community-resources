---
name: Check Balance
description: >
  Look up the balance on one of the customer's accounts so they know what they
  can put down on a car. Activate when the customer asks about balance,
  available funds, savings, or how much money they have.
import_tools:
  - load_customer_profile
  - list_accounts
  - check_balance
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
---

Help the customer check an account balance. Do not invent balances.

If username is missing in project memory, call `@tool.load_customer_profile`.

if: not session.check_balance.account_number
Call `@tool.list_accounts` and present the accounts (type and account number).
Ask which account they want. When they choose, set `account_number` via
`set_fields` to the matching account number. If they already gave a clear
account number, set it without re-asking.

if: session.check_balance.account_number
Call `@tool.check_balance` and report the balance clearly in spoken language
(for example: "Your savings account ending one zero zero two has fifteen
thousand five hundred dollars").

Offer to put that towards a deposit if they are shopping for a car.
