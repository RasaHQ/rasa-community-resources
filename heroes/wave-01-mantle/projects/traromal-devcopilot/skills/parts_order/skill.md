---
name: parts_order
description: >
  Order hardware or licenses for a task, check stock, or raise an approval
  request for restricted items. Activate for hardware orders, stock checks,
  or "I need a monitor".
requires: session.project.authenticated
tool_constraints:
  - check_part_stock:
      requires: session.parts_order.part_no
  - submit_parts_order:
      requires: session.parts_order.part_no
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_parts_order
        utter_on_user_denial: utter_parts_order_cancelled
      on_success: utter_parts_ordered
  - request_part_approval:
      requires: session.parts_order.part_no
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_approval_request
        utter_on_user_denial: utter_approval_cancelled
      on_success: utter_approval_requested
---

Help the developer order hardware or licenses for a task.

First verify identity: @skill.authenticate

Then find the task this order is for: @skill.find_job

Ask which item they need and the quantity. Set part_no and qty.

Once part_no is set, call check_part_stock and report availability and unit
price from the tool result.

if: session.parts_order.part_is_restricted == True
Explain that this item needs manager approval before it can ship. When they
are ready, call request_part_approval.

if: session.parts_order.part_is_restricted == False
When they are ready, call submit_parts_order.

After a successful order, read back the order reference character by character
and ask if anything else is needed.
