---
name: check_itinerary
description: >
  List the traveler's upcoming trips and booking details.
  Activate when they ask what trips they have, for their itinerary,
  or to review bookings.
import_tools:
  - load_customer_profile
  - list_bookings
---

Help the traveler review their itinerary.

If customer details are missing, call @tool.load_customer_profile.

Then call @tool.list_bookings and summarize each trip in short spoken sentences:
trip name, destination, depart date, and booking reference spoken character by
character (for example H T one two three four five).

Ask if they want flight status or a change for any booking.
