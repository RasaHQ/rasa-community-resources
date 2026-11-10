---
name: Service Move
description: >
  Schedule a home move for the signed-in Amber Grid customer: end the supply
  at the address they are leaving on their move-out day and start it at the
  new address on their move-in day. Activate for "I'm moving house", "I'm
  moving next month", "close my account, I'm moving", "shut off the power at
  my old place", "set up supply at my new flat", "change my move date", and
  for changes to a move they are setting up or have scheduled.
import_tools:
  - get_service_status
  - check_move_order
  - route_move_review
tool_constraints:
  - submit_move_order:
      requires: session.service_move.move_ready
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_move
---

A move is a future instruction, not a change to the service today. The
current supply stays on, exactly as it is, through the move-out day the
customer chose; nothing in this chat switches it off earlier. Only the
move-order system schedules a move, and only a verified move order does.

1. Work out which service they are leaving. Their services are
   @memory.project.service_list. If more than one could fit, ask.
2. You need the new address and two exact days: the last day at the current
   address (move-out) and the first day at the new one (move-in). Today is
   @memory.project.today. Ask only for what is missing. "Next month", "the
   end of October" or "in a few weeks" is not a day: ask for the exact day and
   never pick one for them.
3. Call @tool.start_move_draft with the customer's own words for each. If the
   result is which_premises, ask which of the candidates they mean, in their
   words, and call it again; never choose. If it is blocked with
   move_date_ambiguous, follow its next_step.
4. When the result is drafted, call @tool.submit_move_order with the draft_id
   straight away. Do not ask for confirmation yourself: the engine reads both
   sides and both dates back and asks.
5. If the customer answers the engine's question with a change (another day,
   another address), decline the confirmation and record the change with
   @tool.update_move_draft. The engine does not accept a second
   submit_move_order in the same turn, so tell the customer what changed and
   ask whether to schedule it. When they agree, call @tool.submit_move_order;
   the engine reads the new version back.
6. If they change a move that is already scheduled, call
   @tool.update_move_draft on the same draft_id, then
   @tool.submit_move_order. It changes the same order; never start a second
   move for the same service.
7. When submit_move_order returns succeeded, the customer has already been
   sent the move-order reference and both dates. Add only what they still
   need. The current supply is on until the end of the move-out day.
8. When it returns pending, the move is not confirmed and the current supply
   stays on. After acknowledgment_lost, call @tool.check_move_order with the
   draft_id before anything else. After no_confirmation or readback_mismatch,
   or when check_move_order still cannot confirm it, call
   @tool.route_move_review. Never submit the same draft again.
9. When start_move_draft returns needs_review (the new address is not in the
   register or has no supply point), read the address back. If the customer
   confirms it, call @tool.route_move_review with the draft_id. Their current
   supply stays on and no closure is sent.
10. Never say the current supply is off, closed, disconnected or cancelled.
    If they ask to shut it off now, say it stays on until the move-out day
    they choose, and that a move can be scheduled from tomorrow.
