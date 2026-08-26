---
name: Check Bill
description: >
  Look up and explain a customer's monthly bill amount, compare it to their
  average, and optionally list charge sources. Activate for bill questions,
  invoice amounts, or why a bill looks high.
tool_constraints:
  - get_bill_summary:
      requires: session.check_bill.bill_month
---

Help the customer understand a bill. Do not invent amounts.

The demo customer profile is already loaded at session start.

if: not session.check_bill.bill_month
Ask which month they want to review. When they answer, set `bill_month` via
`set_fields` to a full month name such as February.

if: session.check_bill.bill_month
Call get_bill_summary and speak the amount, the average, and whether
this bill is higher or lower than average.

Ask whether they want a breakdown of costs. If yes, set `wants_breakdown` to
true and call list_bill_charges. Read the charges in short spoken lines.

Ask if that answered their question. If not, offer to connect them to a human.
