---
name: Human Handoff
description: >
  Connect the customer to a human insurance agent. Activate when they ask for
  a person, representative, live agent, or say the assistant cannot help.
tool_constraints:
  - create_handoff_ticket:
      requires: session.human_handoff.handoff_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_handoff
        utter_on_user_denial: utter_handoff_cancelled
---

Help the customer reach a human agent.

Ask briefly why they want a human and set `handoff_reason`.
When ready, set `handoff_confirmed` to True and call create_handoff_ticket.
Share the ticket id and say a specialist will join shortly.
Keep it short for voice.
