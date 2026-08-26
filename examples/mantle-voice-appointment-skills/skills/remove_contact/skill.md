---
name: Remove Contact
description: >
  Remove a contact the patient no longer wants saved. Activate when they ask to
  delete, remove, or forget a contact.
import_tools:
  - get_contacts
tool_constraints:
  - delete_contact:
      requires: session.remove_contact.contact_handle
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_remove_contact
        utter_on_user_denial: utter_remove_contact_cancelled
      on_success: utter_contact_removed
---

Help the patient remove a saved contact. Removing a contact cannot be undone, so
the handle has to be certain before anything is deleted.

if: not session.remove_contact.contact_handle
Call get_contacts and ask which contact to remove. When the patient
names one, set `contact_handle` via `set_fields` to that contact's handle from
the tool result — never to a handle you have not seen. If two contacts share a
first name, ask which handle they mean before setting it.

if: session.remove_contact.contact_handle
Call delete_contact.

if: session.remove_contact.contact_removed == False
Tell the patient no contact with that handle is saved. Offer to read the list
back so they can pick a different one, and clear `contact_handle` via
`set_fields` so nothing stale is left behind.
