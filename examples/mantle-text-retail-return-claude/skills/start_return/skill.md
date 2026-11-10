---
name: Start Return
description: >
  Start a return or an exchange for an item on one of the signed-in customer's
  Willow Shop orders. Activate for "I want to return the shirt", "can I
  exchange this for a medium", "I want my money back for order WS-20611",
  "send me a return label", and for changes to a return or exchange the
  customer is setting up.
import_tools:
  - check_return_status
  - route_returns_desk
tool_constraints:
  - submit_return_request:
      requires: session.start_return.selected_resolution
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_return_request
---

Start exactly one return or exchange request the customer has confirmed. A
return label is not a refund: the returns service authorizes the shipment,
the warehouse inspects the item after it arrives, and only then is any refund
decided.

1. Call @tool.find_order_item with the item in the customer's words and the
   order number if they gave one. Their orders are
   @memory.project.order_numbers. If it returns candidates, ask which item.
   If it returns not_found, ask the customer to check the number; never say
   whether an order belongs to someone else.
2. If the item is not eligible, say why in plain words, using the result's
   explanation. Make no label and promise nothing. If a return is already
   authorized, call @tool.check_return_status with the existing reference
   instead of starting another. If the customer asks for an exception, call
   @tool.route_returns_desk with the item_ref.
3. If the customer has not said whether they want a return or an exchange,
   ask them. Do not choose for them, even when they ask you to pick.
4. Call @tool.choose_resolution with the item_ref and their choice; for an
   exchange, include the replacement they named. If it is blocked, follow its
   next_step.
5. When choose_resolution returns recorded, call @tool.submit_return_request
   with the item_ref and the resolution straight away. Do not ask for
   confirmation yourself: the engine reads the request back and asks the
   customer.
6. If the customer answers the engine's question with a change (an exchange
   instead of a return, another replacement, another item), decline the
   confirmation and record the change with @tool.choose_resolution, or
   @tool.find_order_item for another item. The engine does not accept a
   second submit_return_request in the same turn, so tell the customer what
   you recorded and ask whether to request it. When they agree, call
   @tool.submit_return_request; the engine reads the changed request back.
7. When submit_return_request returns succeeded, give the RMA reference, the
   label reference and the next stage. For a return, say that any refund is
   decided after the warehouse receives and inspects the item. Never say a
   refund is issued, approved, processed or on its way. For an exchange, say
   the replacement ships after the returned item is received and inspected.
8. When it returns pending, say the request is not confirmed yet and call
   @tool.check_return_status with its submission_key. If that returns
   authorized, give the references; it is the same request, not a new one.
   If it is still unknown, call @tool.route_returns_desk with the
   submission_key and give the desk reference. Never submit the same request
   again or make another label.
