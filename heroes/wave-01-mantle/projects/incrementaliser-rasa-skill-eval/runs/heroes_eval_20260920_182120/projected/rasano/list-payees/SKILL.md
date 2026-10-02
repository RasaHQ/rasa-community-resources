---
name: list-payees
description: 'List the customer''s authorised payees. Activate when they ask who they
  can pay, which payees they have, or to show transfer recipients.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: list_payees
  rasa_display_name: List Payees
---

# List Payees

## Instructions

Help the customer review authorised payees.

Call get_payees and read the names clearly.
Offer to add a payee, remove a payee, or start a transfer.

## Examples

Follow Instructions; do not invent account details.
