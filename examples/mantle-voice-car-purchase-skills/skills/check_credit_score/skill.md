---
name: Check Credit Score
description: >
  Verify the customer's identity and then look up their credit score for a
  finance application. Activate when they ask about their credit score, credit
  rating, or whether they will be approved for finance.
import_tools:
  - load_customer_profile
  - validate_identity
  - get_credit_score
tool_constraints:
  - get_credit_score:
      requires: session.check_credit_score.identity_verified
---

Help the customer check their credit score. Identity comes first — never pull a
score for someone you have not verified.

If username is missing, call `@tool.load_customer_profile`.

Tell them you need three details to verify who they are, then collect them one
at a time:

1. `full_name` — their full legal name
2. `ssn_last_four` — the last four digits of their social security number
3. `date_of_birth` — in YYYY-MM-DD form

Read digits back slowly when confirming, since this is a voice call.

When all three are collected, call `@tool.validate_identity`.

if: session.check_credit_score.identity_verified == False
Say which detail did not look right and ask for just that one again.
Do not call the credit tool.

if: session.check_credit_score.identity_verified == True
Call `@tool.get_credit_score`. Give the number and the band in one short
sentence, and say it is a demo figure rather than a bureau result.
Offer to work out what they could afford or what a monthly payment would be.
