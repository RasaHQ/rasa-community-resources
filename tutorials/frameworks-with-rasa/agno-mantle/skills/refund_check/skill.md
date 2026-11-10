---
name: refund_check
description: Check whether a fictional Willow Shop return qualifies for an automatic full-refund offer or needs inspection or staff review.
---

Ask for the order reference if it is missing. Call check_return with that
reference. The tool obtains the paid amount and inspection from the supplied
fictional records; do not turn a customer's claim into an inspection result.

For a full_refund_offer, explain the returned amount in GBP pennies as an
offer, not a payment. For awaiting_inspection, explain that an inspection is
needed. For staff_review, explain that the request needs staff review; no
person has been contacted and no queue item has been created by this demo.

For unknown_order, say that the order could not be found for this demo
customer. For unknown_demo_sender, point to the public demo sender names.
Do not invent an amount, promise a discretionary exception or say money moved.
