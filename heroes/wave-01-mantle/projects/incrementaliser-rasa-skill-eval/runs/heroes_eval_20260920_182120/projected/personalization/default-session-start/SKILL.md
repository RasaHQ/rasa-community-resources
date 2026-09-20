---
name: default-session-start
description: 'Conversation opener: look up the customer, then greet them by name.'
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
  - id: greet
    action: utter_greet
:::

## Examples

- Customer: /session_start
