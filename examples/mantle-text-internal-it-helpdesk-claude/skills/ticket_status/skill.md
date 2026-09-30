---
name: Ticket Status
description: >
  Status of one of the signed-in employee's existing helpdesk tickets.
  Activate for "what's happening with IT-TKT-40117", "has my access request
  been approved yet", "is my ticket done", "did the change go through".
import_tools:
  - check_ticket_status
  - route_access_owner
---

Call @tool.check_ticket_status with the ticket reference. If the employee
has none, ask for it.

Report the status exactly as the result gives it. A ticket awaiting approval
has changed nothing and waits for the named owner; urgency does not change
who authorizes access, and you cannot speed up or stand in for the owner's
decision. A completed ticket gives its change reference and scope. If the
result is unknown, call @tool.route_access_owner and give the routing
reference.
