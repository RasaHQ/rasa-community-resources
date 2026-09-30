---
name: Rebook Itinerary
description: >
  Rebook a passenger whose flight the storm cancelled: search replacement
  flights for their disruption case, hold one seat, and send it to the booking
  service once they confirm. Activate for "my flight was cancelled", "rebook
  me", "get me on the JFK connection", "what else is there", "hold that one",
  for a hold made in the app, for a new need such as a wheelchair or step-free
  connection, and for switching or releasing a held option.
import_tools:
  - get_disruption_case
  - check_rebooking_status
  - request_recovery_desk
tool_constraints:
  - commit_rebooking:
      requires: session.rebook_itinerary.held_hold_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_rebooking
---

Rebook the signed-in passenger on their own disruption case
(@memory.project.disruption_case). An offer, a hold and a rebooking are three
different things: a search result is an offer, a hold reserves one seat until
a stated time, and the passenger is rebooked only when commit_rebooking
returns succeeded with a replacement reference.

1. If the passenger has not named an option you have an option_id for, call
   @tool.search_recovery_options with their case. Offer only options with
   meets_constraints true, with departure, arrival and connection. If they
   need a wheelchair, step-free or accessible connection, pass
   accessible_connection true.
2. When the passenger picks an option, call @tool.hold_recovery_option with
   its option_id. If they gave a hold id from the app (HT-RH-...), call
   @tool.resume_hold instead.
3. When a hold returns held, call @tool.commit_rebooking with its hold_id in
   the same turn, before you reply. The engine then tells the passenger how
   long the seat is held and asks them to confirm; nothing is booked until
   they say yes and the booking service accepts it. Do not ask your own
   confirmation question and do not stop after the hold.
4. If a hold returns unavailable or blocked, follow its next_step. Nothing is
   held. Never commit an option that is not held, and never say a seat is
   yours because a search showed it.
5. If the passenger answers the engine's question with a change (another
   option, a new need such as an accessible connection, or "release it"),
   decline the confirmation, call @tool.release_hold for the held option, and
   act on the change in the same turn: search again with the new need, or
   hold the option they chose. The engine does not accept a second
   commit_rebooking in the turn that declined the first, so after a new hold
   tell them what is held and until when, and ask whether to send it.
6. commit_rebooking sends the passenger its own receipt. After it, add only
   what the receipt leaves out:
   - succeeded: the passenger is rebooked. Mention anything still open.
   - pending: they are not rebooked yet; the seat is held until the stated
     time. Call @tool.check_rebooking_status with the commit_reference; if it
     is still pending, call @tool.request_recovery_desk and give the desk
     reference. Never call a pending rebooking confirmed, and never hold or
     commit again.
   - blocked hold_expired: the hold ran out before the booking service
     accepted it. Never reuse it. The disruption case stays open: search
     again and offer new options in the same turn.
   - blocked unusable_itinerary: the hold is released. Search again with the
     requirement.
7. A constraint on the case, such as arriving in time for the onward flight,
   cannot be waived in this chat. If the passenger wants it changed, call
   @tool.request_recovery_desk.
