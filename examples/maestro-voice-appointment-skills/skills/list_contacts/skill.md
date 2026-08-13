---
name: List Contacts
description: >
  List the contacts the patient has saved. Activate when they ask who is on
  their contact list, which contacts they have, or to read their contacts back.
import_tools:
  - get_contacts
---

Help the patient review their saved contacts.

The demo patient is already identified as Jamie Chen in project memory.
Never invent an empty list.

Always call get_contacts before answering. Read `contacts` and
`contact_count` from the tool result. If `contact_count` is greater than zero,
read the names clearly. Only mention a handle when the patient asks for it or
when two contacts share a first name — handles are awkward to listen to.

If `contact_count` is zero, say the list is empty and offer to add a contact.

Offer to add a contact, remove one, or book an appointment.
