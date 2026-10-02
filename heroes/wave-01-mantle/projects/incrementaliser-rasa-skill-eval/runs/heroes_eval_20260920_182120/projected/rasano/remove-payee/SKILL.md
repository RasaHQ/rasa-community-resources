---
name: remove-payee
description: 'Remove an authorised payee the customer no longer wants. Activate when
  they ask to delete, remove, or revoke a payee.

  '
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

Help the customer remove an authorised payee.

If they have not named a payee, call get_payees and ask which one to remove.
Set `payee_name` via `set_fields`, then call remove_payee.
Confirm the result briefly.

## Examples

Follow Instructions; do not invent account details.
