---
name: add-payee
description: 'Add a new authorised payee so the customer can transfer money to them.
  Activate when they want to add, create, or register a new payee or recipient.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: add_payee
  rasa_display_name: Add Payee
---

# Add Payee

## Instructions

Help the customer add an authorised payee. Do not invent account details.

Collect, one at a time:
1. payee_name
2. account_number
3. sort_code
4. payee_type (person or business)
5. reference (short label such as friend, son, utilities)

Call check_payee_exists once you have the name. If the payee already
exists, tell the customer and stop.

When all fields are collected, set `payee_confirmed` to true via `set_fields`,
then call add_payee with the collected values.
Confirm success briefly.

## Examples

Follow Instructions; do not invent account details.
