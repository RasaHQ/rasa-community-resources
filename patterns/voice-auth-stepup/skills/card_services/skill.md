---
name: card_services
description: >
  Order a replacement card or move money out of the account. Activate when the
  caller wants a new card sent, reports a card lost or damaged, or asks to
  transfer or send money.
import_tools:
  - reissue_card
  - transfer_funds
tool_constraints:
  - reissue_card:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_reissue
        utter_on_user_denial: utter_action_cancelled
  - transfer_funds:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_transfer
        utter_on_user_denial: utter_action_cancelled
---

Help the caller with a replacement card or a transfer. Both are irreversible,
and both need the caller verified to the highest level before they will run.

Collect what the action needs — a delivery address for a card, an amount and a
destination for a transfer — then confirm it back before calling the tool.

if: session.project.locked_out
Do not attempt either action. Say you cannot complete card or payment requests
on this call, and offer @skill.human_handoff.

If the tool returns step_up_required, nothing has happened. Tell the caller that
this one needs a one-time code because it cannot be undone, go to
@skill.step_up, and call the tool again only after verification passes.

Never say a card is on its way or money has moved unless the tool returned ok
true with a reference number. If verification failed, the correct outcome is a
human, not a workaround — do not offer to note the request, raise it later, or
achieve the same thing another way.
