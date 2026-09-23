---
name: reminders
description: >
  Set personal reminders and list open ones. Activate when they ask to be
  reminded about something, or ask what reminders they have.
---

Help the developer manage personal reminders by voice.

if: not session.reminders.reminder_text
When they want a new reminder, ask what it should say and set reminder_text.
Ask in how many minutes it is due, or take it from what they said, and set
due_minutes. Confirm in one short sentence, then call create_reminder and
say it is set.

if: session.reminders.reminder_text
After creating a reminder, clear reminder_text so the next one starts fresh.

When they ask what reminders they have, call list_reminders and read each one
aloud with its due time. Keep every answer short enough for voice.
