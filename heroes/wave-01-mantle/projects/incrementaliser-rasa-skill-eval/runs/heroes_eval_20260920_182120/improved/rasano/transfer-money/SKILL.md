---
name: transfer-money
description: Transfer money from a customer account to an authorised payee. Activate
  for send money, pay someone, make a transfer, or move funds.
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

Transfer money from one of the customer's accounts to an authorised payee. Do not invent accounts, payees, or balances: every value comes from the customer or a tool call.

## Collect transfer details

1. Ask for the source account. If needed, call list_accounts and let them choose. Done when `account_number` is set to an account the customer picked.
2. Ask who they want to pay. If needed, call get_payees. Set `payee_name`, then call check_payee_exists. Done when check_payee_exists has returned for the chosen payee.

if: session.transfer_money.payee_exists == False
Tell them that payee is not authorised yet. Invoke `@skill.add_payee` so they can add the payee. After that skill completes, continue the transfer with the new payee name. Done when the payee is authorised and `payee_name` is set.

3. Ask for the amount and set `amount`. Amount must be greater than zero. Call check_sufficient_funds. Done when check_sufficient_funds has returned for the chosen amount and account.

if: session.transfer_money.sufficient_funds == False
Explain there are not enough funds and ask if they want a different amount or account. Do not process the payment. Done when the customer picks a new amount or account, or ends the transfer.

## Timing

4. Ask whether the payment should be immediate or scheduled. Set `timing`. Done when `timing` is "immediate" or "scheduled".

if: session.transfer_money.timing == "immediate"
Set `order_confirmed` to true and call process_transfer. Done when process_transfer has returned.

if: session.transfer_money.timing == "scheduled"
Collect `payment_date` (YYYY-MM-DD, must be in the future), set `order_confirmed` to true, and call schedule_transfer. Done when schedule_transfer has returned.

## Examples

- Customer: Send 50 dollars to Robert from my current account.
