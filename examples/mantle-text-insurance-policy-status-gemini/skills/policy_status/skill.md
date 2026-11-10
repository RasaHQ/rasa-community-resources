---
name: Policy Status
description: >
  Policy status - whether a HarborCover policy is active, lapsed or in force,
  and its effective dates. Activate for "is my policy active", "when does my
  policy end", "is my renters policy still valid".
import_tools:
  - open_coverage_question
---

Help the caller check the status of one of their policies. Their policy
numbers are @memory.project.policy_numbers. If they do not say which policy,
ask, naming the products rather than reading every number.

Call @tool.get_policy_status with the policy number. Report the state, the
effective dates, when the status service observed it, and the status
reference.

The state says whether the policy is in force. It does not say whether a
particular loss is covered. If the caller asks whether a loss is covered,
call @tool.open_coverage_question with the policy and their description of
the loss, then give them its reference and next review step.
