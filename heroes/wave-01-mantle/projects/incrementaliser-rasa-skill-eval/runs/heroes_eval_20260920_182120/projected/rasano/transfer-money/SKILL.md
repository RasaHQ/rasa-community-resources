---
name: transfer-money
description: 'Transfer money from one of the customer''s accounts to an authorised
  payee. Activate for send money, pay someone, make a transfer, or move funds.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: transfer_money
  rasa_display_name: Transfer Money
---

# Transfer Money

## Instructions

Help the customer transfer money. Do not invent accounts, payees, or balances.

## Collect transfer details

Ask for the source account. If needed, call list_accounts and let them
choose. Set `account_number`.

Ask who they want to pay. If needed, call get_payees.
Set `payee_name`. Call check_payee_exists.

if: session.transfer_money.payee_exists == False
Tell them that payee is not authorised yet. Invoke `@skill.add_payee` so they
can add the payee. After that skill completes, continue the transfer with the
new payee name.

Ask for the amount and set `amount`. Amount must be greater than zero.
Call check_sufficient_funds.

if: session.transfer_money.sufficient_funds == False
Explain there are not enough funds and ask if they want a different amount or
account. Do not process the payment.

## Timing

Ask whether the payment should be immediate or scheduled. Set `timing`.

if: session.transfer_money.timing == "immediate"
When details are ready, set `order_confirmed` to true and call
process_transfer.

if: session.transfer_money.timing == "scheduled"
Collect `payment_date` (YYYY-MM-DD, must be in the future), set
`order_confirmed` to true, and call schedule_transfer.

## Examples

- Customer: Send 50 dollars to Robert from my current account.
