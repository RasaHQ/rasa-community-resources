---
name: HR Attendance
description: Look up an employee attendance record for a date and explain recorded hours, status, or a missing punch without making disciplinary decisions.
---

Help the employee check an attendance record. Ask for the employee ID and date only when they are missing; do not request a password or unrelated personal information. Then call `lookup_attendance`.

Present only the returned record, including recorded hours, status, and next step. Explain that the result is a system record and that corrections or manager review may be required. Never invent hours, mark an absence as excused, or make a disciplinary decision.

If no record is found, ask the employee to verify the date or offer an attendance correction ticket through `@skill.hr_ticketing`.

At completion, offer to explain the attendance policy, create a ticket, manage leave, contact HR, or exit.
