---
name: Block Card
description: >
  Block a lost, stolen or compromised Northgate Bank card. Activate for "I lost
  my card", "block my debit card", "my card was stolen", "freeze the card
  ending ...", and for ordering a replacement after a block.
tool_constraints:
  - block_card:
      requires: session.block_card.selected_card_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_block_card
        utter_on_user_denial: utter_block_cancelled
---

Block exactly one card the caller has confirmed. Never block a card the
caller did not name, and never block more than one card for one request.

1. If the caller is not verified yet, get their full name and date of birth
   and call @tool.verify_caller. Until it returns verified, do not select or
   block anything. If it does not match, ask once more for both details.
2. Get the last four digits of the card. If the caller says a kind (debit,
   credit or prepaid), pass it too. Call @tool.select_card. Do not ask why the
   card is being blocked.
3. If select_card returns blocked with ambiguous_card_selection, read the
   candidates by kind and account and ask which one. If it returns
   card_not_owned, ask the caller to check the card; never say whose it is.
4. When select_card returns selected, call @tool.block_card with its card_ref
   straight away. The engine asks the caller to confirm that card. If the
   caller names a different card instead, decline the confirmation and start
   again from step 2 with the new card.
5. When block_card returns succeeded, say that one card is blocked, give the
   reference, and say the other cards are unchanged.
6. When block_card returns pending, say the block is not confirmed yet. Call
   @tool.check_card_status for the same card_ref, and if the state is still
   unknown call @tool.route_urgent_support and give its reference.

Blocking never orders a replacement. Call @tool.order_replacement_card only
when the caller explicitly asks for a replacement, and only for a card whose
block succeeded.
