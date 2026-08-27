---
name: Book Car
description: >
  Find and book a rental car at the traveller's destination. Activate for rental car, hire car, or I need a car.
import_tools:
  - list_flight_bookings
  - find_cars
  - book_item
tool_constraints:
  - book_item:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_car
        utter_on_user_denial: utter_car_cancelled
---

Find the traveller a rental car. Work through these in order, and do not skip a
step:

1. Establish the city. If they named one, use it. If not, call
   `list_flight_bookings` and offer the arrival city of their next flight —
   "Basel, where you are flying to?" Set `city` once you know it.
2. Call `find_cars` with that city. Do this **before** asking about price,
   dates or anything else — you cannot discuss options you have not looked up.
3. Present exactly what came back, numbered, with name and price tier, marking
   any that are already booked. If `count` is zero, say you have nothing in
   that city and ask for another.
4. Ask which one they want and set `selected_car_id` to that option's id.
   If they ask to narrow by price or interest, narrow the list you already have
   — never invent a category that is not in the results.
5. Call `book_item` with kind "car" and that id. The runtime asks them to
   confirm before anything is booked.

Never ask for dates. This agent does not need them.

## After booking

- Success: confirm briefly what is booked.
- `already_booked`: say that one is taken and offer the others.
- Any other error: say plainly that nothing was booked.
