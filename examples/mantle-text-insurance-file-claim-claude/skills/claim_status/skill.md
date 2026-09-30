---
name: Claim Status
description: >
  Where a claim or a submitted report already stands. Activate for "what's
  happening with my claim", "did my claim go through", "what do you still
  need for HC-CLI-40718".
import_tools:
  - check_claim_submission
  - route_claims_intake
---

Call @tool.check_claim_submission with the claim-intake reference or draft id
the customer gives. Report the stage, the material received and what is still
needed exactly as the result gives them. Coverage is not decided until a
claims handler decides it; never say a loss is covered or will be paid. If the
result is unknown, or the customer wants something the result cannot answer,
call @tool.route_claims_intake and give the desk reference.
