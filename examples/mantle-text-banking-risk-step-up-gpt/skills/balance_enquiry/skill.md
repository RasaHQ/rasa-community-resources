---
name: Balance Enquiry
description: >
  Balance enquiry - the balance of one of the customer's Northgate accounts.
  Activate for "what's my balance", "how much is in my savings", "can I see
  my current account".
import_tools:
  - get_balance
---

The customer's accounts are @memory.project.accounts. If they do not say
which account, ask. Call @tool.get_balance and give the balance and the time
it was read.

A balance enquiry is information only. It does not verify the customer for a
transfer, and it does not make a later transfer any easier.
