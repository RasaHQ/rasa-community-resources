---
name: Session Start
description: "Conversation opener: look up the customer, then greet them by name."
routing:
  engine_managed: true
---

:::ordered_block id=main
steps:
  - id: identify
    execute_tool: get_customer_profile
  - id: greet
    action: utter_greet
:::
