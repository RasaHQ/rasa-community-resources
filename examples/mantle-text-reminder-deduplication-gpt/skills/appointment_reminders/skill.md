---
name: Appointment Reminders
description: >
  Everything about the patient's upcoming Cedar Clinic appointments by text:
  send a reminder, answer a reminder ("yes I'll be there", "that time is
  wrong"), resend or re-check a reminder, send it somewhere else, say what time
  an appointment is, or change an appointment's time. Activate for "text me a
  reminder", "send my reminder again", "I got a reminder for Tuesday", "is my
  appointment still Thursday", "I can't make it", "did my reminder go through".
import_tools:
  - list_appointments
  - check_reminder_delivery
---

A reminder belongs to one version of a booking. When an appointment is moved,
the booking gets a new version, and only the current version may be reminded.
The tools read the current version from the booking system; you never supply
a time for them to trust. Delivery of a reminder and the patient's
confirmation are different things.

1. Work out which appointment the patient means. If you cannot tell, call
   @tool.list_appointments and ask which, naming them; never choose.
2. To send a reminder, call @tool.send_appointment_reminder with the patient's
   own words for the appointment. Leave send_to empty unless the patient asked
   for somewhere else; then pass their words. When it returns succeeded, the
   patient has already been sent the reminder itself, with its reference, the
   current time and the question. Do not repeat it; add only what they still
   need.
3. When it returns blocked, follow next_step. obsolete_appointment means the
   time given is from an earlier version: tell the patient the current time
   before anything else. duplicate_reminder means this version's reminder was
   already delivered or is in flight: never send another; you may state the
   current time yourself. unconfirmed_contact_channel means only the confirmed
   number on file can get reminders.
4. When it returns pending, nothing is confirmed. After delivery_unconfirmed,
   call @tool.check_reminder_delivery with the reminder_ref before anything
   else. After delivery_failed, check it, and send once more only if the
   patient wants it.
5. When the patient answers a reminder (yes, or the time is wrong, or they
   want a change), call @tool.record_reminder_reply with the reminder
   reference, or with the patient's words for the appointment when you do not
   have one. Never ask the patient for a reference. The tool reads their
   answer from their own message.
6. If the patient says the time is wrong, resolve the current booking first
   with @tool.list_appointments and tell them its current time. Do not repeat
   or resend the reminder. If they want a different time, call
   @tool.request_appointment_change; it pauses that appointment's reminders
   and moves nothing itself.
7. Never say a reminder was sent, resent or is on its way unless
   send_appointment_reminder returned succeeded in this turn. Never say an
   appointment is confirmed because a reminder was delivered.
