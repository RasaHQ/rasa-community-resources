---
name: Session Start
description: "Conversation opener: greet the visitor."
routing:
  engine_managed: true
---

:::ordered_block id=main
steps:
  - id: greet
    action: utter_greet
:::
