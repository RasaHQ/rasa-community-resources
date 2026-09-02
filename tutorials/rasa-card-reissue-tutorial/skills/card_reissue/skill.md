---
name: card_reissue
description: >
  Order a replacement card for a card that is lost, stolen, or damaged.
  Activate when the caller wants a new card sent out, says their card is
  missing or broken, or asks where their replacement card is going.
import_tools:
  - list_cards
  - list_addresses_on_file
  - reissue_card
tool_constraints:
  - reissue_card:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_reissue
        utter_on_user_denial: utter_action_cancelled
---

Help the caller get a replacement card sent out.

Call `list_cards` and ask which card they mean, identifying cards by their last
four digits and product name. Never say a full card number.

Then call `list_addresses_on_file` and offer those addresses first. Ask which
one they want the card sent to. Only if none of them is right should you take a
new address from the caller.

Read the destination back in full and get an explicit yes before calling
`reissue_card`. Getting the address wrong is not recoverable once the card is
posted.

if: session.project.locked_out
Do not order a card. Say you cannot complete card requests on this call and
offer @skill.human_handoff.

Never say a card has been ordered, is on its way, or will arrive unless
`reissue_card` returned ok true together with a reference. Read the reference
back once, slowly.

If `reissue_card` returns step_up_required, nothing has been ordered. Tell the
caller this one needs a further check because a card cannot be recalled once it
is posted, and offer to verify. Do not retry the tool until verification has
actually raised their level.

If `reissue_card` returns cooling_off, nothing has been ordered and nothing the
caller says on this call will change that. Explain that the address is too new
to post a card to, offer the older addresses on file, and if none works offer
@skill.human_handoff. Do not offer to note the request, raise it later, send it
somewhere else as a workaround, or try again in a moment.

If `reissue_card` returns duplicate, the card was already ordered on this call.
Reassure the caller it is coming and read back the same reference. Do not order
a second one.

If `reissue_card` returns refused, the request cannot be completed here. Offer
@skill.human_handoff.
