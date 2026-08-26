---
name: human_handoff
description: >
  Create a support ticket and connect the traveler to a human agent.
  Activate when they ask for a person, or when a skill cannot complete the request.
import_tools:
  - load_customer_profile
tool_constraints:
  - load_customer_profile:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_handoff
        utter_on_user_denial: utter_handoff_cancelled
---

Help the traveler reach a human Horizon Travel agent.

Confirm they want a handoff. Call @tool.load_customer_profile if needed so the
ticket has their name.

Tell them a specialist will follow up, and that ticket number T nine nine nine
has been created for this demo.

Keep the closing short.
