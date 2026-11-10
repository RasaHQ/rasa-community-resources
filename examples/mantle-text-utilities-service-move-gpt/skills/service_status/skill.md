---
name: Service Status
description: >
  Read the current supply at one of the signed-in customer's addresses, and
  the state of a move already requested. Activate for "is my power still on",
  "has my move gone through", "what's happening with move order AG-MOV-...",
  "when does my supply at Wren Street end".
import_tools:
  - get_service_status
  - check_move_order
  - route_move_review
---

Call @tool.get_service_status with the address or service the customer
names. Their services are @memory.project.service_list. For a move they
requested, call @tool.check_move_order with the draft id or move-order
reference.

Report exactly what the tools return. The current supply is on unless the
result says otherwise; a scheduled move-out is a future day, not a closure
now. If a move is still not confirmed, call @tool.route_move_review. Never
send or change a move from here; for a change, use the move skill.
