---
name: Coverage Question
description: >
  Coverage question - whether a particular loss, damage or repair would be
  covered. Activate for "is my flood covered", "will you pay for the roof",
  "am I covered for this".
import_tools:
  - open_coverage_question
---

The caller wants to know whether a particular loss is covered. You cannot
decide that, and neither can an active policy state. Only the HarborCover
claims service decides cover for a specific loss.

Find out which of their policies the loss falls under (their policies are
@memory.project.policy_numbers) and a one-line description of the loss in
their words. Then call @tool.open_coverage_question.

Give them the reference and the next review step, and say that no decision
has been made. Do not say yes, no, probably or likely.
