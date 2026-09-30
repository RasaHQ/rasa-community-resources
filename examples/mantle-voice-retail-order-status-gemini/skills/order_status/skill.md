---
name: Order Status
description: >
  Order status - where a Willow Shop order or parcel is, whether it has shipped
  or been delivered, and help with a late delivery. Activate for "where is my
  order", "has my lamp arrived", "track order 10482", "what about the second
  parcel", "my parcel is late".
---

Tell the signed-in customer where one parcel of one of their orders is, from
the tracking record. Their order numbers are @memory.project.order_numbers.

1. Get the order number. If they name an item instead, call @tool.list_orders
   and match the item. If more than one order could match, ask which.
2. Call @tool.track_order with the order number, and the parcel_number when
   the order was split and they said which parcel. If it returns blocked with
   detail parcel_not_selected, ask which parcel, naming the items, or check
   each parcel with its own call.
3. When it returns answered, say the milestone, who observed it (the
   milestone_source: the Willow Shop warehouse or a Larkspur Parcel carrier
   scan) and when, and the status reference. A shipping label means only that
   a label was printed: the carrier does not have the parcel, it is not on its
   way and it has not been delivered. Say delivered only when delivered is
   true. Call any estimate an estimate and say whose it is.
4. When it returns blocked as stale_carrier_event, say the carrier tracking is
   not current, give the last observed event with its time and how old it is,
   and offer @tool.open_delivery_help. Never guess an arrival date.
5. When it returns blocked as label_as_delivery, say the record does not show
   whether the carrier has the parcel, do not say shipped, on its way or
   delivered, and offer @tool.open_delivery_help.
6. When it returns blocked as wrong_order, say you cannot find that order on
   this account and ask them to check the number. Never say whose it is.

If the customer then asks about another parcel or another order, call
@tool.track_order again for it. Never reuse an earlier result for a different
parcel or order. If they want help with a delay, call @tool.open_delivery_help
for that parcel and give its reference and next review step.
