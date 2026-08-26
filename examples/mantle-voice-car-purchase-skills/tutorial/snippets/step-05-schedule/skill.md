---
name: Schedule Dealer Appointment
description: >
  Book a visit to a Rasa Motors dealer for a test drive, paperwork, collection,
  or a part-exchange valuation. Activate when the customer wants to come in,
  book a slot, arrange a test drive, or see a car in person.
import_tools:
  - load_customer_profile
  - query_available_slots
  - book_appointment
tool_constraints:
  - book_appointment:
      requires: session.schedule_dealer_appointment.selected_slot_date and session.schedule_dealer_appointment.selected_slot_time
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_appointment
        utter_on_user_denial: utter_appointment_cancelled
      on_success: utter_appointment_booked
---

Help the customer book a dealer visit. Dealers open Monday to Friday only.

If username is missing, call `@tool.load_customer_profile`.

## Make sure there is a car to visit

if: not session.project.car_model and not session.reserve_car.selected_model
The customer has not put a car aside yet, and a dealer visit is about a
specific vehicle. Tell them you will hold a car first, then invoke
`@skill.reserve_car`. When that skill completes, continue booking the visit
with the model and dealer it reserved.

if: session.project.car_model and not session.project.dealer_name
Ask which dealer they want to visit and set `dealer_choice` via `set_fields`.

## Purpose of the visit

Ask what the visit is for. Valid purposes: test_drive, paperwork, collection,
valuation. Set `appointment_purpose`.

## Pick a slot

Call `@tool.query_available_slots`. Read out two or three slots at most, as a
weekday and a time — for example "Tuesday at eleven". Ask which one suits them.

When they choose, set `selected_slot_date` to the slot date in YYYY-MM-DD form
and `selected_slot_time` to the start time in HH:MM form.

if: not session.schedule_dealer_appointment.selected_slot_date
Do not guess a date. If none of the slots work, offer the next few instead.

## Book it

Read the dealer, the day, and the time back in one short sentence. When they
agree, call `@tool.book_appointment`.

Give them the appointment reference and remind them to bring their driving
licence and proof of address.
