---
name: check-balance
description: 'Look up the balance on one of the customer''s bank accounts. Activate
  when the customer asks about balance, available funds, or how much money is in an
  account.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: check_balance
  rasa_display_name: Check Balance
---

# Check Balance

## Instructions

Help the customer check an account balance. Do not invent balances. The
customer's identity is already loaded in project memory.

if: not session.check_balance.account_number
Call list_accounts and present the accounts (type and account number).
Ask which account they want. When they choose, set `account_number` via
`set_fields` to the matching account number. If they already gave a clear
account number, set it without re-asking.

if: session.check_balance.account_number
Call check_balance and report the balance clearly in spoken language
(for example: "Your current account ending in 6789 has four thousand nine
hundred twenty-three dollars and sixty-seven cents").

## Examples

- Customer: What's my balance?
