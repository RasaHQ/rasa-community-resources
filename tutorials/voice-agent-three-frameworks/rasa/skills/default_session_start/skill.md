---
# concern: agent-logic
name: Session Start
description: "Conversation opener: greet the caller and ask for identification."
routing:
  engine_managed: true
---

:::ordered_block id=main
name: default_session_start
description: "Greet the caller."
steps:
  - id: greet
    action: utter_greet
:::
