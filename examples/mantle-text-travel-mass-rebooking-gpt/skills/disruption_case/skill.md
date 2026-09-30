---
name: Disruption Case
description: >
  The passenger's disruption case: what was cancelled, what is still booked,
  whether a replacement is committed, pending or held, and the recovery desk.
  Activate for "what's happening with my cancelled flight", "am I rebooked",
  "is my new flight confirmed", "check HT-CM-...", "I want someone to change my
  Funchal flight".
import_tools:
  - get_disruption_case
  - check_rebooking_status
  - request_recovery_desk
---

Answer from the tools only. The passenger's case is
@memory.project.disruption_case.

For the state of the case, call @tool.get_disruption_case. The passenger is
rebooked only if replacement is set. An active hold is not a rebooking; say
until when it is held. An expired hold cannot be used.

For a rebooking that came back pending, call @tool.check_rebooking_status
with its commit reference. If it is still pending, call
@tool.request_recovery_desk and give the desk reference. Never say a pending
rebooking is confirmed.

When the passenger wants a constraint on the case changed (the onward
flight, the latest arrival), call @tool.request_recovery_desk with a one-line
reason. Do not promise a flight or a time.
