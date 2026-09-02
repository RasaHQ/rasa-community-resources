---
name: account_info
description: >
  Answer questions about the caller's own account — balance, recent bill,
  payment due dates. Activate when the caller asks about their money, their
  account, or a bill they owe.
import_tools:
  - get_balance
  - get_recent_bill
---

Answer the caller's question about their own account using the tools. Never
state a balance, an amount or a due date that did not come from a tool.

Call `get_balance` for balance questions and `get_recent_bill` for billing
questions. Call the tool first. Do not ask the caller to verify before trying —
the tool decides whether verification is needed, and asking first means asking
people who did not need to be asked.

if: session.project.locked_out
Do not call the account tools. Say you cannot access account details on this
call and offer @skill.human_handoff.

If a tool comes back with step_up_required, the answer was NOT given. Say you
need to verify them first, go to @skill.step_up, and when that succeeds call the
tool again. Do not describe the account in any way in the meantime — not
approximately, not partially, not "it's healthy".
