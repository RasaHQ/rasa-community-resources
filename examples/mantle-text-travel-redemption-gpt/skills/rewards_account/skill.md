---
name: Rewards Account
description: >
  Rewards account - the member's points balance and earlier redemptions,
  including a redemption that took points without a booking. Activate for
  "how many points do I have", "check redemption HT-RD-...", "my points were
  taken but I have no ticket", "why is my balance lower".
import_tools:
  - get_points_balance
  - get_redemption_status
  - request_rewards_desk_review
---

Answer questions about the member's points and earlier redemptions from the
tools only. Their account is @memory.project.rewards_account.

For a balance, call @tool.get_points_balance with their account. Report the
balance, any points reserved by a hold, and any redemption listed in
open_mismatches.

For an earlier redemption, call @tool.get_redemption_status with its
reference. If the member does not know the reference, read the balance: an
unreconciled redemption is listed there. Report the points state and the
booking state separately. A points deduction alone does not mean a reward was
booked.

When a redemption took points without a booking, do not redeem the reward
again to fix it. Call @tool.request_rewards_desk_review with its reference
and give the desk case and the next review step. Do not promise when the
points come back.
