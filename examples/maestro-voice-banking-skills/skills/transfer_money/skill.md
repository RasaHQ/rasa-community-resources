---
name: Transfer Money
description: >
  Transfer money from one of the customer's accounts to an authorised payee.
  Activate for send money, pay someone, make a transfer, or move funds.
import_tools:
  - list_accounts
  - get_payees
  - check_payee_exists
tool_constraints:
  - process_transfer:
      requires: session.transfer_money.order_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_transfer
        utter_on_user_denial: utter_transfer_cancelled
      on_success: utter_transfer_complete
  - schedule_transfer:
      requires: session.transfer_money.order_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_scheduled_transfer
        utter_on_user_denial: utter_transfer_cancelled
---

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
