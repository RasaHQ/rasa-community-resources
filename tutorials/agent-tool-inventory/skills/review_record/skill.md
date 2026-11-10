---
name: review_record
description: Inspect an invented review record.
import_tools:
  - record_review
tool_constraints:
  - record_review:
      requires_confirmation:
        enabled: true
---

Use the review tool when the user asks. Continue with @block.finish_review.

:::ordered_block id=finish_review
steps:
  - id: record
    execute_tool: record_review
    next: END
:::
