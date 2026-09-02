---
name: Check Balance
description: >
  Report the balance of one of the customer's accounts (checking or savings).
  Activate only when the customer asks about a balance, how much money they
  have, or what is left in an account.
tool_constraints:
  - get_balance:
      requires: session.check_balance.selected_account_id
---

Report one account balance accurately. Never state a balance that did not come
from the `get_balance` tool.

if: not session.check_balance.selected_account_id
The customer has two accounts. Follow these steps in order:

1. Call `fetch_accounts` to load the real account list.
2. Present the accounts by name and last four digits, and ask which one they mean.
3. When they choose, set `selected_account_id` via `set_fields` to the matching
   account id from the tool result.

If they already named an account unambiguously (by name or last four), skip the
question and set `selected_account_id` directly from the tool result.

if: session.check_balance.selected_account_id
Call `get_balance` for the selected account and state the balance in one
sentence, including the account name. If the tool reports an error, say plainly
that you could not retrieve the balance — do not substitute a number.
