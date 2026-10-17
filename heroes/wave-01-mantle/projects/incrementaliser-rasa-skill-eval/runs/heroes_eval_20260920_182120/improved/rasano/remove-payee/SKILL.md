---
name: remove-payee
description: Remove an authorised payee. Activate when the customer asks to delete,
  remove, or revoke a payee.
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: remove_payee
  rasa_display_name: Remove Payee
---

# Remove Payee

## Instructions

Remove an authorised payee the customer no longer wants.

1. If the customer has not named a payee, call get_payees and ask which one to remove. Done when the customer has picked one payee from the list.
2. Set `payee_name` via `set_fields`, then call remove_payee. Done when remove_payee returns a result for that payee.
3. Confirm the result briefly. Done when the customer knows whether the payee was removed.

## Examples

Follow Instructions; do not invent account details.
