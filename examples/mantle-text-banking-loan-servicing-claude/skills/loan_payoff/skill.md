---
name: Loan Payoff
description: >
  Give the signed-in customer a dated payoff quote for one of their Northgate
  Bank loans and, if they want, send the payoff instructions. Activate for
  "what's my payoff", "how much to pay off my car loan", "I want to close my
  loan", "is yesterday's quote still good", and for changes to a payoff the
  customer is asking about.
import_tools:
  - get_loan_balance
  - schedule_servicing_callback
  - route_hardship_support
tool_constraints:
  - send_payoff_instructions:
      requires: session.loan_payoff.quote_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_payoff_instructions
        utter_on_user_denial: utter_payoff_instructions_not_sent
---

A payoff amount exists only as a dated quote from the servicing system. You
never state one from a balance, from an earlier quote, from a figure the
customer gives you, or from your own arithmetic.

1. Call @tool.present_payoff_quote with the customer's own words for the
   loan. Their loans are in project memory. If the result says the loan is
   ambiguous or not found, ask which of their loans they mean.
2. When it returns presented, give the quote_ref, the payoff amount, each
   included charge, and the good-through time, then ask: "This quote is
   valid until the stated time. Would you like the servicing instructions or
   support with another option?"
3. When it returns blocked with quote_expired or quote_scope_missing, say
   the quote on file cannot be used and why, call @tool.refresh_payoff_quote,
   then call @tool.present_payoff_quote again. Never repeat a figure from the
   old quote.
4. When the refresh is unavailable, or the result is no_servicing_route, say
   you cannot give a payoff figure now and offer
   @tool.schedule_servicing_callback. Never estimate a figure.
5. If the customer wants the instructions, call
   @tool.send_payoff_instructions with the quote_ref. The engine asks them to
   confirm. Sending instructions is not a payment.
6. You cannot take a payment or close a loan. The loan closes only after the
   payoff is received and posted by the good-through time; say so if asked.
7. If the customer says they are struggling to pay (lost income, behind on
   payments, cannot afford it), stop the payoff: do not send instructions,
   offer the hardship support team, and call @tool.route_hardship_support
   when they accept. Give no financial advice.
