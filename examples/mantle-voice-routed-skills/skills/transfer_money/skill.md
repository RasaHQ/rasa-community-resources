---
name: Transfer Money
description: >
  Move money between the caller's own checking and savings accounts. Activate
  for transfer, move money, or shift funds between my accounts.
tool_constraints:
  - process_transfer:
      requires: session.transfer_money.transfer_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_transfer
        utter_on_user_denial: utter_transfer_cancelled
      on_success: utter_transfer_complete
---

Help the caller move money between their own two accounts. Never invent
balances; check them with the tool.

Collect the source account, the destination account, and the amount. Set
`from_account`, `to_account` and `amount` as the caller gives them — pass their
own words for the accounts through, the tool normalises them. Source and
destination must be different accounts.

Call `check_transfer` once you have all three. It confirms the accounts resolve
and that the source has enough money.

if: session.transfer_money.sufficient_funds == False
Say plainly that the source account does not hold that much, give the balance
the tool returned, and ask whether they want a smaller amount or a different
account. Do not process the transfer.

if: session.transfer_money.sufficient_funds == True
Read the whole transfer back for confirmation — amount, from, to — then set
`transfer_confirmed` and call `process_transfer`. This is money moving; the
caller confirms before it happens, not after.
