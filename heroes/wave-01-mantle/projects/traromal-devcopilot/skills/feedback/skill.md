---
name: feedback
description: >
  Record, list, or review beta feedback about DevPilot. Activate when the
  developer says something was wrong, wants to report a bug, or asks about
  previous feedback.
---

Help the developer capture useful beta feedback.

For new feedback, collect one item at a time in this order:

:::ordered_block id=collect_feedback
steps:
  - id: collect_category
    instructions: Set category to bug, usability, safety, voice, or feature.
    complete_when: session.feedback.category
  - id: collect_severity
    instructions: Set severity to critical, high, medium, or low.
    complete_when: session.feedback.severity
  - id: collect_description
    instructions: Capture what happened.
    complete_when: session.feedback.description
  - id: collect_expected
    instructions: Capture what should have happened.
    complete_when: session.feedback.expected
  - id: collect_actual
    instructions: Capture what DevPilot actually did.
    complete_when: session.feedback.actual
:::

Then call record_feedback. For list or review requests, call list_feedback.
Never claim feedback was saved unless the tool confirms it.
