---
name: Return Status
description: >
  Status of a return or exchange that already exists. Activate for "has my
  refund come through", "did you get my return", "where is my refund for the
  chinos", "I lost my return label".
import_tools:
  - check_return_status
  - route_returns_desk
---

Call @tool.check_return_status with the RMA reference or submission key if
the customer has one, otherwise with the order number and the item in their
words. Their orders are @memory.project.order_numbers.

Report each stage exactly as the result gives it: authorization, shipment,
inspection, refund and replacement. A refund that is not_decided has not been
issued, approved or scheduled; say it is decided after inspection. If the
customer lost their label, give the label reference from the result: it is
the same label, and no new return is started. If the result is unknown, or
the customer wants something the result cannot answer, call
@tool.route_returns_desk and give the desk reference.
