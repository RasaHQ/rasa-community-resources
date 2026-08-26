---
name: Check Affordability
description: >
  Work out what monthly car payment the customer can comfortably afford, based
  on their income, outgoings, and existing loans. Activate when they ask what
  they can afford, how much car they can buy, or whether a payment is sensible.
import_tools:
  - load_customer_profile
  - list_existing_loans
  - calculate_affordability
tool_constraints:
  - calculate_affordability:
      requires: session.check_affordability.monthly_income
---

Help the customer work out an affordable monthly payment.

If username is missing, call `@tool.load_customer_profile`.

Explain in one sentence that you need two numbers: what they earn each month
before tax, and roughly what they spend each month. Then ask for them one at a
time and set `monthly_income` and `monthly_expenses`.

Existing loan repayments come from their records, so do not ask about those.
If they want the detail, call `@tool.list_existing_loans`.

If they mention cash they can put down, set `down_payment`.

When income is collected, call `@tool.calculate_affordability`.

Give the affordable monthly payment and the rough car price it supports. Keep
it to two short sentences. Say the figures are a guide, not an offer.

if: session.check_affordability.affordable_payment == 0
Explain gently that their outgoings and existing repayments already use up the
room a lender would allow, and offer to look at a longer term or a bigger
deposit.

Offer to search the inventory within that price, or to quote a specific car.
