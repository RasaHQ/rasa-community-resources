---
name: Transfer Money
description: >
  Send money - a transfer to one of the customer's saved payees or between
  their own accounts, including changing the amount or payee of a transfer in
  progress, finishing one started earlier, and the verification step a
  transfer needs. Activate for "send 200 pounds to Mum", "pay my landlord",
  "move money to savings", "finish the transfer I started this morning".
import_tools:
  - get_balance
---

Send exactly one transfer at a time, with the verification its own risk
assessment requires. The customer's accounts are @memory.project.accounts and
their saved payees are @memory.project.payees. This chat cannot add a payee.

1. Find out the source account, the destination and the amount. Ask for
   anything missing. Then call @tool.assess_transfer with exactly those.
2. Follow the assessment's next_step:
   - required_level 1: read back the amount, destination and account, and on
     the customer's yes call @tool.submit_transfer.
   - required_level 2: say "This transfer needs an additional verification
     step. Would you like to continue or speak with the team?" If they
     continue, call @tool.start_step_up. When they type the code, call
     @tool.submit_step_up_code with it. When it returns verified, call
     @tool.submit_transfer.
   - required_level 3: do not start a step-up. Call
     @tool.suspend_transfer_and_route and give its reference.
3. Always pass submit_transfer the assessment_ref of the current assessment
   and the same account, destination and amount it was assessed for.
4. If the customer changes the account, destination or amount at any point,
   even after a code was sent or verified, start again at step 1 with a new
   assess_transfer. The old code and the old verification do not carry over;
   a new step-up sends a new code.
5. If a code is locked, or the customer would rather speak with the team,
   call @tool.suspend_transfer_and_route. Nothing is sent.

A transfer is sent only when submit_transfer returns succeeded: give the
amount, destination and decision_reference. Otherwise say nothing was sent.
