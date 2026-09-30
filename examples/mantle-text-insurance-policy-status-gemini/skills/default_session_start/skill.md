---
name: Session Start
description: "Conversation opener: bind the identified caller, then greet."
routing:
  engine_managed: true
import_tools:
  - load_caller_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the caller's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_caller_profile
  - id: greet
    action: utter_greet
:::
