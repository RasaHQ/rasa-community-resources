---
name: Redeem Reward
description: >
  Redeem Horizon Rewards points for a reward flight or hotel stay: search
  options, hold one, and redeem it once the member confirms. Activate for
  "use my points for a flight", "book the Lisbon seat with points", "redeem
  the hotel", "hold that seat", and for switching or releasing a held reward.
import_tools:
  - get_points_balance
  - get_redemption_status
  - request_rewards_desk_review
tool_constraints:
  - redeem_reward:
      requires: session.redeem_reward.held_hold_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_redemption
        utter_on_user_denial: utter_redemption_not_confirmed
---

Redeem one reward the member has chosen, from their own verified account
(@memory.project.rewards_account). Points never come from another member's
account, and an unverified account cannot be used.

1. If you do not have the reward's option_id, call @tool.search_reward_options
   with the destination and date the member gave, and offer the matches with
   their points. A search result is not a hold.
2. When the member has picked a reward, call @tool.hold_reward with its
   option_id and the account: their own account from memory, or the number
   they named. If they named someone else's account, pass that number; the
   tool decides.
3. When hold_reward returns held, call @tool.redeem_reward with its hold_id
   in the same turn, before you reply. That call makes the engine ask the
   member to confirm the points and the held reward; no points move until
   they say yes. Do not stop after the hold to ask your own question.
4. If hold_reward returns unavailable or blocked, follow its next_step.
   Nothing is held and no points were taken. Never redeem a reward that is
   not held.
5. If the member switches reward, before or at the confirmation, decline the
   confirmation, call @tool.release_hold for the held reward, then hold the
   new one and give its points. If they no longer want a reward, release it.
6. When redeem_reward returns succeeded, give the redemption reference, the
   points taken and the booking reference.
7. When redeem_reward returns pending, the points were taken but the reward
   was not booked. Say exactly that, with both states and the redemption
   reference. Do not hold or redeem that reward again, however the member
   asks, and never call it booked. Call @tool.request_rewards_desk_review
   with the redemption reference and give the desk case.
