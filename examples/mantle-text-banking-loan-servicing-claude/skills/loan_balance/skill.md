---
name: Loan Balance
description: >
  Read a loan's principal balance and next payment. Activate for "what's the
  balance on my car loan", "how much do I still owe on the personal loan",
  "when is my next payment".
import_tools:
  - get_loan_balance
---

Call @tool.get_loan_balance with the customer's words for the loan. Give the
principal balance with its as-of date and the next payment. The balance is
not a payoff amount; if the customer wants to pay the loan off, the payoff
skill gives a dated quote.
