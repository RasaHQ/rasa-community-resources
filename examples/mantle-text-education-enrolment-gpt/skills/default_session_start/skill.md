---
name: Session Start
description: "Conversation opener: bind the signed-in applicant, then greet."
routing:
  engine_managed: true
import_tools:
  - load_applicant_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the applicant's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_applicant_profile
  - id: greet
    action: utter_greet
:::
