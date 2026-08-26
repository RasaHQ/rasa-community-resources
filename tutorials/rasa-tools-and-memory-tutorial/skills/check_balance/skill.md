---
name: Check Balance
description: >
  Tell the caller the balance of one of their accounts. Activate for balance,
  how much is in my account, or available funds.
import_tools:
  - get_customer_info
---

Give the caller a balance.

Ask which account they mean if they have not said, then call `fetch_balance`.

`fetch_balance` reads the signed-in customer from project memory, so it is the
authority on whether the caller is verified. If it returns `not_authenticated`,
tell the caller you need to verify them first and let the Authenticate skill
run. Never state a balance in that case.

When it succeeds, call `get_customer_info` so you can greet them by name. That
tool is shared with other skills, so it is imported above rather than living in
this skill's folder.

Read back the balance with its currency, and nothing else.
