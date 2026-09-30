---
name: Session Start
description: "Conversation opener: greet the shopper."
routing:
  engine_managed: true
---

:::ordered_block id=main
name: default_session_start
description: "Greet the shopper."
steps:
  - id: greet
    action: utter_greet
:::
