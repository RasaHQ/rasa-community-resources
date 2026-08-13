---
name: change_booking
description: >
  Change or cancel an existing Horizon Travel booking.
  Activate for date changes, cancellations, or "I need to change my trip".
requires: session.project.authenticated
tool_constraints:
  - cancel_booking:
      requires: session.project.selected_booking_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_cancel_booking
        utter_on_user_denial: utter_cancel_aborted
      on_success: utter_booking_cancelled
---

Help the traveler change or cancel a booking.

First verify identity: @skill.authenticate

Then find the booking: @skill.find_booking

Ask what they want to change.

if: session.change_booking.change_type == "cancel"
Explain that cancellation is permanent. When they are ready, call
cancel_booking with the selected booking reference.

if: session.change_booking.change_type == "date_change"
Explain that date changes for non-flexible fares may include a fee.
Collect the preferred new date, confirm, then say a human agent must complete
paid reissues and offer @skill.human_handoff.

if: session.change_booking.change_type == "seat_change"
Explain that free seat selection opens 48 hours before departure, or they can
pay for extra-legroom seats now via Manage Trip. Offer to connect to a human
if they want an agent to do it.

After a successful cancellation, read back the booking reference character by
character and ask if anything else is needed.
