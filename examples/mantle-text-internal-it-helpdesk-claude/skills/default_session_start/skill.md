---
name: Session Start
description: "Conversation opener: bind the signed-in employee, then greet."
routing:
  engine_managed: true
import_tools:
  - load_session_employee
---

:::ordered_block id=main
name: default_session_start
description: "Load the signed-in employee's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_session_employee
  - id: greet
    action: utter_greet
:::
