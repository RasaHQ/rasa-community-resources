---
name: Outage Status
description: >
  Outage status - whether there is a known network outage where one of the
  customer's services is, and when it should be fixed. Activate for "is there
  an outage", "my internet is down, is it you", "when will the outage be
  fixed", "is the network down in Millbrook".
import_tools:
  - check_area_outage
  - run_line_diagnostics
  - request_technician_visit
---

The customer wants to know about an outage. This skill never changes a
device: it has no reboot or reset.

Their services are @memory.project.service_1, @memory.project.service_2
and @memory.project.service_3. If they do not say which one,
ask, naming the label and address rather than reading ids.

Call @tool.check_area_outage for the service. Report what it returns:

- outage: the incident reference, the cause, when it started and the
  estimated restore time. Say a reboot or reset cannot fix it.
- clear: say there is no known outage there, and offer read-only
  @tool.run_line_diagnostics.
- unknown: say the outage status cannot be confirmed right now and give the
  last known observation time. Offer to check again later or
  @tool.request_technician_visit. Do not suggest rebooting or resetting.
