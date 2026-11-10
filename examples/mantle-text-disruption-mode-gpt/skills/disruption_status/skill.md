---
name: Disruption Status
description: >
  Status information during the storm disruption: what is happening, whether
  a flight is cancelled, and where a seat hold the passenger already has
  stands, by its hold id. Activate for "what's going on with the storm", "is
  my Denver flight cancelled", "is hold HT-HLD-4K7M still valid", "did my
  hold expire".
import_tools:
  - get_incident_status
  - check_hold
  - release_hold
---

Call @tool.get_incident_status, with the passenger's words for a booking if
they named one, and give the incident revision, what it says and the
booking's flight status. Incident status is information: never say it holds
or promises a seat.

For a hold the passenger already has, call @tool.check_hold with its hold
id and say exactly what it returns: active until its expiry, expired, or
released. An active hold is not a confirmed journey. If the passenger
rejects a held option, call @tool.release_hold with its hold id. Never
place a new hold from here.
