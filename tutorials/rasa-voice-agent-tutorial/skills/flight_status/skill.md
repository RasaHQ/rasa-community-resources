---
name: flight_status
description: >
  Look up live flight status for a Horizon Travel booking.
  Activate for delays, gates, cancellations, or "is my flight on time".
import_tools:
  - get_flight_status
tool_constraints:
  - get_flight_status:
      requires: session.flight_status.booking_ref
---

Help the traveler check flight status.

Ask for their booking reference if booking_ref is not set. Accept spoken forms
like "H T one two three four five" and normalize to HT12345 in memory as
booking_ref.

Once booking_ref exists, call @tool.get_flight_status.

if: session.flight_status.flight_status == "delayed"
Tell them the delay in minutes and the gate if available. Offer to help with
a booking change via @skill.change_booking.

if: session.flight_status.flight_status == "cancelled"
Apologize briefly. Explain that rebooking options are available and offer
@skill.change_booking or @skill.human_handoff.

if: session.flight_status.flight_status == "on_time" or session.flight_status.flight_status == "boarding"
Confirm the status, scheduled time, and gate in one or two short sentences.

Keep every answer short enough for voice.
