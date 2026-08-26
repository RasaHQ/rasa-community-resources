---
name: View Policies
description: >
  List the customer's insurance policies with premium and coverage limit.
  Activate when they ask what policies they have, coverage amounts, or premiums.
import_tools:
  - list_policies
---

Help the customer review their policies. Do not invent policy numbers or amounts.

Call list_policies and present each policy clearly for voice:
policy type, policy number, premium, and coverage limit.
Ask if they want to file a claim on one of them or need anything else.
