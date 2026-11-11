---
name: default-session-start
description: 'Session start: look up the customer profile, then greet the customer
  by name.'
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: default_session_start
  rasa_display_name: Session Start
---

# Session Start

## Instructions

:::ordered_block id=main
steps:
  - id: identify
    execute_tool: get_customer_profile
    done_when: The customer's profile is loaded and their name is known.
  - id: greet
    action: utter_greet
    done_when: The customer has been greeted by the name from their profile.
:::

Greet with the name from the profile only. Do not invent a name or any other customer detail; if the profile has no name, greet without one.

## Examples

- Customer: /session_start
