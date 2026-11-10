---
name: Account Balance
description: >
  Balance of one of the signed-in customer's accounts. Activate for "what's my
  balance", "how much is in savings", "what can I spend in checking".
import_tools:
  - get_balance
---

The caller's accounts are @memory.project.account_names. Ask which one if
they have not said, then call @tool.get_balance. Give the available balance,
the posted balance if it differs (holds explain the gap), and the time it was
read. Say it is the balance now, not a promise that a later transfer will be
funded.
