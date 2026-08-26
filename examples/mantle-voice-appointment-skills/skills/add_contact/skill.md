---
name: Add Contact
description: >
  Save a new contact for the patient. Activate when they want to add, save, or
  register a contact, or to store someone's handle.
import_tools:
  - get_contacts
tool_constraints:
  - save_contact:
      requires: session.add_contact.contact_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_add_contact
        utter_on_user_denial: utter_add_contact_cancelled
      on_success: utter_contact_added
---

Help the patient save a contact. Do not invent names or handles.

Collect, one at a time:
1. `contact_name` — what the patient calls this person, for example Joe
2. `contact_handle` — their handle, for example at Joe Myers

Handles are dictated over the phone, so read the handle back letter by letter
before you save it. If the patient does not know the handle, say you cannot save
the contact without one and offer to come back to it later.

Optionally set `relationship` if the patient volunteers one, such as friend,
sister, or doctor. Do not interrogate them for it.

When the name and handle are both collected, set `contact_confirmed` to true via
`set_fields`, then call save_contact.

if: session.add_contact.contact_exists == True
Tell the patient that contact is already saved and do not add it again. Offer to
read their contact list back with get_contacts.
