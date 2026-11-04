---
name: add-payee
description: Adding a new authorised payee so the customer can transfer money to them.
  Use when the customer wants to add, create, or register a payee or recipient.
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

Add an authorised payee. Do not invent account details; collect every value from the customer.

1. Collect these fields one at a time, until all five are answered:
   - payee_name
   - account_number
   - sort_code
   - payee_type (person or business)
   - reference (short label such as friend, son, utilities)
2. Call check_payee_exists once you have payee_name. Done when the call returns: if the payee already exists, tell the customer and stop.
3. When all five fields are collected, set `payee_confirmed` to true via `set_fields`, then call add_payee with the collected values. Done when add_payee returns.
4. Confirm success briefly.

## Examples

Follow Instructions; do not invent account details.
