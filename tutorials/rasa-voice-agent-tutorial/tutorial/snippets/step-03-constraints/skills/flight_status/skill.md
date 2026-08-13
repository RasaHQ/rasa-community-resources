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

Once booking_ref exists, call @tool.get_flight_status and report the status,
gate, and any delay in short spoken sentences.
