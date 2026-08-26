---
name: Session Start
description: "Conversation opener: load the patient's clinic profile, then greet."
routing:
  engine_managed: true
import_tools:
  - load_customer_profile
---

:::ordered_block id=main
name: default_session_start
description: "Conversation opener: load the patient's clinic profile, then greet."
steps:
  - id: load_profile
    execute_tool: load_customer_profile
  - id: greet
    action: utter_greet
:::
