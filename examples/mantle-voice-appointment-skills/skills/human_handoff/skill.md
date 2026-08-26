---
name: Human Handoff
description: >
  Connect the patient to a member of the clinic team. Activate when they ask for
  a person, receptionist, or nurse, or say the assistant cannot help.
tool_constraints:
  - create_handoff_ticket:
      requires: session.human_handoff.handoff_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_handoff
        utter_on_user_denial: utter_handoff_cancelled
---

Help the patient reach the clinic team.

Ask briefly why they want to speak to someone and set `handoff_reason`.
When ready, set `handoff_confirmed` to true and call create_handoff_ticket.
Share the ticket number and say someone from the clinic will call them back
shortly.

If the patient describes a medical emergency, tell them to hang up and call the
emergency services immediately. Do not put them in a callback queue.
