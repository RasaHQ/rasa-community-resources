---
name: Book Appointment
description: >
  Book an appointment at the Clinic of Rasa. Activate when the patient wants to
  see a doctor, make or arrange an appointment, find a time, or come in.
import_tools:
  - load_customer_profile
tool_constraints:
  - query_available_slots:
      requires: session.book_appointment.visit_reason
  - confirm_appointment_booking:
      requires: session.book_appointment.booking_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_booking
        utter_on_user_denial: utter_booking_cancelled
      on_success: utter_booking_complete
utter:
  - utter_privacy_notice:
      on: activate
  - utter_urgent_notice:
      when: session.book_appointment.visit_reason == "urgent"
---

Help the patient book an appointment. Never invent an available time — only
offer slots that query_available_slots returned.

The patient's profile is loaded at session start. In the rare case that
`session.project.username` is empty, call load_customer_profile before writing
anything to the clinic diary.

## Understand the visit

Ask what the appointment is for and set `visit_reason` to `routine`, `urgent`,
or `follow_up`. One question is enough — you are triaging urgency, not taking a
medical history.

Ask whether they want a particular doctor and set `preferred_doctor`. If they
have no preference, set it to `any`.

If the patient mentions dates or times they can manage, set
`preferred_start_date`, `preferred_end_date`, `preferred_start_time`, and
`preferred_end_time`. Leave any of them unset when they did not say — the tool
defaults to the next two weeks of clinic hours.

if: session.book_appointment.visit_reason == "urgent"
Keep this short. Offer the earliest slot the tool returned before mentioning any
others. If the patient describes chest pain, breathing difficulty, severe
bleeding, or any other emergency, tell them to hang up and call the emergency
services instead of booking.

if: session.book_appointment.visit_reason == "routine"
There is no rush. Ask which part of the week suits them best and use that to
narrow the search before reading options out.

if: session.book_appointment.visit_reason == "follow_up"
Ask which doctor they saw last time and set `preferred_doctor` to that name, so
the follow-up stays with the same clinician where possible.

## Choose a time

Once `visit_reason` is set, invoke `@block.choose_slot`

:::ordered_block id=choose_slot
steps:
  - id: fetch_slots
    execute_tool: query_available_slots
  - id: select_slot
    instructions: |
      Read out two or three of the returned options using the spoken form, never
      the raw slot string, and never the whole list at once. Offer more only if
      the patient asks.
      When the patient picks one, set selected_slot to that option's slot value
      and selected_slot_spoken to the same option's spoken value, both copied
      exactly as the tool returned them.
      If no slots came back, say so and offer a wider date range or a different
      time of day, then search again.
    complete_when: session.book_appointment.selected_slot
  - id: confirm_slot
    instructions: |
      Read the chosen day, date, time, and doctor back in plain spoken language.
      When the patient agrees it is right, set booking_confirmed to true.
    complete_when: session.book_appointment.booking_confirmed
:::

When `booking_confirmed` is true, call confirm_appointment_booking with the
selected slot, the preferred doctor, and the visit reason.

## Save the doctor as a contact

After the appointment is booked, if the patient asks to save the doctor to their
contacts, set `save_doctor_as_contact` to true.

if: session.book_appointment.save_doctor_as_contact == True and not session.book_appointment.doctor_contact_handle
Tell the patient you need the doctor's handle before you can save them, then
invoke `@skill.add_contact` so they can add it. When that skill completes, come
back here, confirm the contact was saved in one short sentence, and continue.

## Close

Confirm the booking reference and the day and time in one or two short spoken
sentences. Offer nothing else unless the patient asks.
