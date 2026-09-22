---
name: default-session-start
description: 'Session start: load the customer profile, then greet the user.'
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
name: default_session_start
description: "Load the demo customer's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_customer_profile
    done_when: The customer profile is loaded into project memory.
  - id: greet
    action: utter_greet
    done_when: The greeting has been sent to the user.
:::

## Examples

Follow Instructions; do not invent account details.
