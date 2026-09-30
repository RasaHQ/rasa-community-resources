---
name: Session Start
description: "Conversation opener: bind the signed-in passenger, then greet."
routing:
  engine_managed: true
import_tools:
  - load_passenger_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the passenger's profile and disruption case into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_passenger_profile
  - id: greet
    action: utter_greet
:::
