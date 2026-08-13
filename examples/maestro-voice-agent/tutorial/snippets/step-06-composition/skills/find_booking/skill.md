---
name: find_booking
description: >
  Find and select a specific booking by reference or trip name.
  Used as a sub-skill when another skill needs a selected booking.
import_tools:
  - list_bookings
tool_constraints:
  - get_booking:
      requires: session.find_booking.booking_ref
---

Help the traveler identify which booking they mean.

If they already gave a booking reference, set booking_ref and call
get_booking.

Otherwise call list_bookings, read the trip names aloud, and ask which
one. Set booking_ref from their choice, then call get_booking.

When selected_booking_ref is set, confirm the trip name in one short sentence
and return to the parent skill.
