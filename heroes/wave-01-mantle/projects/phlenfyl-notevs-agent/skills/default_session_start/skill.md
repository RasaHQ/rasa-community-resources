---
name: Session Start
description: "Conversation opener — overridden to skip the built-in greeting so the user's first real message goes straight to the right skill instead of being consumed by a canned greeting turn."
routing:
  engine_managed: true
---

:::ordered_block id=main
steps:
  - id: skip
    noop: true
    next: END
:::
