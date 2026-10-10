---
name: Session Start
description: "Conversation opener: identify the caller, then greet."
routing:
  engine_managed: true
import_tools:
  - load_caller
---

:::ordered_block id=main
name: default_session_start
description: "Load the caller from their number, then greet them."
steps:
  - id: identify
    execute_tool: load_caller
  - id: greet
    action: utter_greet
:::
