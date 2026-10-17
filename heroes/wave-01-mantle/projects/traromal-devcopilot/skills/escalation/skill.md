---
name: escalation
description: >
  Raise an escalation ticket to the on-call desk, including emergency response.
  Activate when they ask to reach on-call, when a task is critical, or when
  a skill cannot complete the request.
import_tools:
  - load_developer_profile
tool_constraints:
  - raise_escalation:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_escalation
        utter_on_user_denial: utter_escalation_cancelled
      on_success: utter_escalation_raised
---

Help the developer raise an escalation to the on-call engineer.

Confirm they want an escalation. Call load_developer_profile if needed so the
ticket has their name.

Tell them the on-call engineer has been notified, and that ticket E nine nine
nine has been created for this demo.

Keep the closing short.
