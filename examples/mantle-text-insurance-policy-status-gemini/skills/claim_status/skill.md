---
name: Claim Status
description: >
  Claim status - the recorded stage and next review step of an existing
  HarborCover claim. Activate for "where is my claim", "what's happening with
  claim CLM-24-0871", "has my claim been decided".
import_tools:
  - open_coverage_question
---

Help the caller check an existing claim. Their claim numbers are
@memory.project.claim_numbers. If they do not say which claim, ask, naming
the losses rather than reading every number.

Call @tool.get_claim_status with the claim number. Report the stage, when it
was recorded, when the status service observed it, the next review step and
the status reference.

Only a result with decision_type coverage_decision contains a decision about
cover, and that decision applies to that claim alone. For any other stage,
say plainly that no coverage decision has been made yet.

If the result is blocked as stale, give the last known stage with its
timestamp, say it may have changed, and offer @tool.request_case_team_callback.
If it is blocked because the decision type is not labeled, do not interpret
the stage and offer the same callback.

If the caller then asks whether a different loss is covered, do not reuse
this claim's status or decision. Call @tool.open_coverage_question for the
new loss.
