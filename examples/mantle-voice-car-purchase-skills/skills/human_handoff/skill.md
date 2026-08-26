---
name: Human Handoff
description: >
  Connect the customer to a Rasa Motors sales specialist. Activate when they ask
  for a person, a salesperson, a manager, or say the assistant cannot help.
import_tools:
  - create_handoff_ticket
tool_constraints:
  - create_handoff_ticket:
      requires: session.human_handoff.handoff_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_handoff
        utter_on_user_denial: utter_handoff_cancelled
---

Help the customer reach a human specialist.

Ask briefly why they want a person and set `handoff_reason`.
When ready, set `handoff_confirmed` to true and call `@tool.create_handoff_ticket`.
Share the ticket id and say a specialist will join in about five minutes.
