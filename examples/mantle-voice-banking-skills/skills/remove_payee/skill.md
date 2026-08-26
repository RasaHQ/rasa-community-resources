---
name: Remove Payee
description: >
  Remove an authorised payee the customer no longer wants. Activate when they
  ask to delete, remove, or revoke a payee.
import_tools:
  - get_payees
tool_constraints:
  - remove_payee:
      requires: session.remove_payee.payee_name
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_remove_payee
        utter_on_user_denial: utter_remove_payee_cancelled
---

Help the customer remove an authorised payee.

If they have not named a payee, call get_payees and ask which one to remove.
Set `payee_name` via `set_fields`, then call remove_payee.
Confirm the result briefly.
