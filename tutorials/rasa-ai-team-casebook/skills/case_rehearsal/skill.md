---
name: case_rehearsal
description: >
  Run or inspect one fictional casebook scenario when the learner supplies its
  case identifier, for example contextual-handoff or banking-transfer.
import_tools:
  - rehearse_case
  - inspect_case
  - record_case_intake
---

Confirm the case identifier with the learner, then call `rehearse_case`.
For driver arrival, absence reporting, cancellation or an unmatched outage
report, confirm that the learner wants that independent intake, then call
`record_case_intake`. Report its intake reference as a recorded observation or
request only. It does not grant loading clearance, approve a swap, close an
account or establish an outage cause. An ineligible offer or guarded action must
not prevent the learner from choosing the independent intake.
Describe the returned status and reason as a synthetic lab result. If a result
is pending, explain that the action may already be recorded. Call `inspect_case`
when the learner asks to check its state. If it remains pending or unknown, stop
automatic attempts and ask the learner to use the case's recovery instructions.

If input is unsupported, ask the learner to choose an identifier from the
casebook index. Never invent a service receipt or treat missing evidence as
approval. When a learner corrects the requested case, confirm the correction
before running it. Do not imply that the previous case was undone.
