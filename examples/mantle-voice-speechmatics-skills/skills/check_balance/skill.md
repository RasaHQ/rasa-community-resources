---
name: Check Balance
description: >
  Read out the balance on the caller's checking or savings account. Activate
  when they ask about balance, available funds, or how much is in an account.
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_type
---

Help the caller check a balance. Never invent a number — the tool is the only
source.

if: not session.check_balance.account_type
Ask which account they mean: checking or savings. When they answer, set
`account_type` via `set_fields` to what they actually said — the tool
normalises "check", "current", "sav" and similar itself, so pass their words
through rather than guessing at a canonical value. If they already named an
account clearly, set it without re-asking.

if: session.check_balance.account_type
Call `check_balance` and read the result back in spoken language, for example
"your checking account has two thousand four hundred fifty dollars and
seventy-five cents". Then ask whether there is anything else.
