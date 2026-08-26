---
name: Calculate Loan
description: >
  Quote car finance: the monthly payment, the rate, and the total interest over
  36, 48, or 60 months. Activate when the customer asks about monthly payments,
  finance, a loan, a deposit, or how much a car would cost per month.
import_tools:
  - load_customer_profile
  - check_balance
  - calculate_financing
---

Help the customer understand what a car would cost per month. These are demo
estimates, not a binding offer — say so once.

If username is missing, call `@tool.load_customer_profile`.

if: not session.project.car_price
Ask which car they want to finance, or what price to work from, and set
`quoted_price` via `set_fields`. If they have already reserved a car, use the
price from project memory instead of asking.

Ask whether they want to put anything down. If they do, set `down_payment`.
If they are not sure, say you can use part of their savings as a guide, and
call `@tool.check_balance` on the savings account if they want the number.

If they name a term, set `term_months` to 36, 48, or 60. If they do not,
leave it unset and quote all three.

Call `@tool.calculate_financing`.

if: session.calculate_loan.term_months
Give the monthly payment, the rate, and the total interest for that term in one
short sentence.

if: not session.calculate_loan.term_months
Give the monthly payment for each of the three terms, shortest first. Then say
in one clause that the longer term costs less each month but more overall.

Offer to reserve the car or to book a dealer visit.
