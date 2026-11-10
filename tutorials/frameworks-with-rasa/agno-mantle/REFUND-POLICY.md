# Fictional automatic-refund policy

This example extends fictional Willow Shop’s customer-support journey. The
records are invented; this policy is not taken from a real retailer.

An automatic offer uses the amount paid in the order record, in GBP pennies.
The model does not supply an amount or an inspection result.

Apply these rules in order:

1. An unknown order or one belonging to another customer returns the same
   unknown-order result, without disclosing its price or inspection.
2. A return received after day 30 needs staff review. Day 30 is included in
   the automatic window; delivery is day 0.
3. Inside that window, a missing inspection needs an inspection before an offer.
4. A recorded sealed return or confirmed defect qualifies for the full amount
   paid. Other recorded conditions need staff review.

The received day, paid amount and inspection come from service-owned records.
A customer’s explanation may be relevant to staff, but does not become an
inspection or a different paid amount. Staff review is a decision status here;
this example does not contact a person or create a real queue item. An offer
does not issue a payment.

Tests of this function establish these rules only. They do not establish
whether a model calls the function, reports its result faithfully or treats a
customer fairly before calling it. A real channel must establish the customer
identity separately; public demo sender names are not authentication.
