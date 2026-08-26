---
name: Add Payee
description: >
  Add a new authorised payee so the customer can transfer money to them.
  Activate when they want to add, create, or register a new payee or recipient.
import_tools:
  - load_customer_profile
  - check_payee_exists
  - add_payee
tool_constraints:
  - add_payee:
      requires: session.add_payee.payee_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_add_payee
        utter_on_user_denial: utter_add_payee_cancelled
---

Help the customer add an authorised payee. Do not invent account details.

If username is missing, call `load_customer_profile`.

Collect, one at a time:
1. payee_name
2. account_number
3. sort_code
4. payee_type (person or business)
5. reference (short label such as friend, son, utilities)

Call `check_payee_exists` once you have the name. If the payee already
exists, tell the customer and stop.

When all fields are collected, set `payee_confirmed` to true via `set_fields`,
then call `add_payee` with the collected values.
Confirm success briefly.
