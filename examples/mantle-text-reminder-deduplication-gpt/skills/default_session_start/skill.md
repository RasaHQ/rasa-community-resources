---
name: Session Start
description: "Conversation opener: bind the patient this SMS thread belongs to, then greet."
routing:
  engine_managed: true
import_tools:
  - load_patient_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the patient's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_patient_profile
  - id: greet
    action: utter_greet
:::
