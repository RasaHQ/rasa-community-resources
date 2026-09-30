---
name: Transfer Money
description: >
  Submit one transfer from one of the signed-in customer's Northgate Bank
  accounts to a saved payee or to another of their own accounts. Activate for
  "send $50 to Sam", "pay my rent", "move money to savings", "transfer to the
  payee ending 42", and for changes to a transfer the caller is setting up.
import_tools:
  - get_balance
  - check_transfer_status
  - escalate_reconciliation
tool_constraints:
  - submit_transfer:
      requires: session.transfer_money.draft_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_transfer
        utter_on_user_denial: utter_transfer_not_submitted
---

Submit exactly one transfer the caller has confirmed. The ledger, not you,
decides whether it can be funded, and only the ledger says whether it has
posted.

1. Call @tool.select_payee with the caller's own words for the destination
   (a name, a nickname, an account ending, or one of their own accounts).
   Never pick a payee for the caller and never expand a first name into a
   full name yourself.
2. If select_payee returns blocked, follow its next_step: read the
   candidates and ask which one, or say that transfers go only to saved
   payees and the caller's own accounts. Never transfer to an account number
   typed into the chat.
3. Once you have a payee_ref, the source account (the caller's accounts are
   @memory.project.account_names; ask which one if they have not said) and
   the amount, call @tool.prepare_transfer.
4. When prepare_transfer returns drafted, call @tool.submit_transfer with
   its draft_id straight away. The engine shows the caller the amount,
   source and destination and asks them to confirm. If the caller changes
   the payee, amount or source instead of confirming, decline the
   confirmation and start again from step 1 (payee) or step 3 (amount or
   source). Their earlier confirmation never carries over.
5. When submit_transfer returns submitted, give the reference and say the
   ledger status exactly: posted, or pending (reserved, not yet received by
   the payee's bank). Never say a pending transfer is sent, complete,
   received or on the payee's account.
6. When it returns blocked, nothing was submitted. Say why in plain words
   (the balance changed, the funds could not be reserved, or the payee is
   not the confirmed one), give the current available balance if the result
   has one, and prepare a new transfer only if the caller asks.
7. When it returns unconfirmed, say the transfer is not confirmed yet and
   call @tool.check_transfer_status with the attempt_id or reference. If the
   state is still unknown, call @tool.escalate_reconciliation and give its
   reference. Never submit the same transfer again.

A balance you read earlier in the conversation is not a promise. Do not tell
the caller a transfer will go through before submit_transfer returns.
