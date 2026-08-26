---
name: Check Existing Loans
description: >
  List the customer's current loans and what they repay each month. Activate
  when they ask about existing finance, current repayments, outstanding debt,
  or what they still owe.
import_tools:
  - load_customer_profile
  - list_existing_loans
---

Help the customer review their existing loans. Do not invent lenders or amounts.

If username is missing, call `@tool.load_customer_profile`.

Call `@tool.list_existing_loans`.

Read out each loan as the lender, the purpose, and the monthly payment. Then
give the total monthly repayment in one short sentence.

If there are no loans, say so plainly.

Offer to check what they could afford on top of these commitments.
