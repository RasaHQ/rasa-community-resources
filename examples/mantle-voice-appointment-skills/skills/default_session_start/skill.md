---
name: Session Start
description: "Conversation opener: load the patient profile, then greet the user."
routing:
  engine_managed: true
import_tools:
  - load_customer_profile
---

:::ordered_block id=main
name: default_session_start
description: "Load the demo patient's profile into project memory, then greet."
steps:
  - id: load_profile
    execute_tool: load_customer_profile
  - id: seed_demo_identity
    set_memory:
      username: Jamie Chen
      patient_id: PT-10432
      email: jamie.chen@example.com
      phone: "0771 234 5678"
  - id: greet
    action: utter_greet
:::
