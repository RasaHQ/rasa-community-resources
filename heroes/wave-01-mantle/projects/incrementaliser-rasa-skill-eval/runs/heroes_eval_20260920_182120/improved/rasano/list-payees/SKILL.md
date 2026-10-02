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

1. Call get_payees. Done when the tool returns the payee list.
2. Read every returned name clearly. Done when each payee from the response has been read out.
3. Offer to add a payee, remove a payee, or start a transfer. Done when the customer has picked an option or declined.

## Examples

Follow Instructions; do not invent account details.
