---
name: Open Dispute
description: >
  Open a dispute for a Northgate Bank card transaction the caller does not
  recognise. Activate for "I don't recognise a charge", "there's a payment I
  didn't make", "dispute a transaction", "I want my money back for a charge",
  and for blocking a card during that call.
tool_constraints:
  - file_dispute:
      requires: session.open_dispute.selected_transaction_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_dispute
        utter_on_user_denial: utter_dispute_not_filed
---

Record the caller's dispute for exactly one transaction they confirmed. A
dispute receipt is not a finding of fraud and never a refund.

1. If the caller is not verified yet, get their full name and date of birth
   and call @tool.verify_caller. Until it returns verified, do not look up or
   dispute anything. If it does not match, ask once more for both details.
2. Get what the caller knows about the charge: merchant, amount in rupees,
   date, card ending. Call @tool.select_transaction with what they said.
3. If select_transaction returns blocked with candidates, read them and ask
   which one. If it returns no candidates, ask the caller to check the
   merchant, amount and date; never say whether a charge belongs to someone
   else.
4. When select_transaction returns selected, call @tool.file_dispute with its
   transaction_ref and the caller's statement in their own words. The engine
   reads the charge back and asks the caller to confirm. If the caller says
   they recognise the charge, or names a different one, decline the
   confirmation; for a different charge start again from step 2.
5. When file_dispute returns succeeded, give the dispute reference and the
   next review step, and say no refund or credit has been decided.
6. When file_dispute returns pending, say the dispute is not confirmed yet.
   Call @tool.check_dispute_status with its submission_key. If that returns
   recorded, give the reference. If it is still unknown, call
   @tool.route_disputes_desk and give the desk reference. Never file the same
   charge again.

Blocking a card is separate. Call @tool.request_card_block only when the
caller asks for a card to be blocked, and give its reference apart from the
dispute reference.
