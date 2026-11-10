---
name: Session Start
description: "Conversation opener: bind the signed-in customer, then greet."
routing:
  engine_managed: true
import_tools:
  - load_customer_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the customer's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_customer_profile
  - id: greet
    action: utter_greet
:::
