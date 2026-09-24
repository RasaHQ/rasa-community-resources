---
name: check_loyalty_rewards
description: >
  Check customer loyalty points, rewards balance, membership status,
  tier benefits (Regular, Silver, Gold), and redeem loyalty points for drinks.
  Activate when the customer asks about loyalty points, points balance, rewards,
  membership tier, or provides an account ID like CUST-1001 to check rewards.
import_tools:
  - check_loyalty_account
  - redeem_loyalty_reward
---

Help the customer check their loyalty rewards balance and redeem member perks.

Ask for their Customer ID (e.g. CUST-1001), phone number, or name if not already identified.
Call @tool.check_loyalty_account with their customer identifier.

Once their profile is retrieved, announce their current points balance and tier status.

if: session.project.loyalty_tier == "Gold"
Welcome them warmly as a Gold VIP member. Mention that they receive double points on specialty roasts and complimentary flavor shots on all barista beverages.

if: session.project.loyalty_tier == "Silver"
Thank them for their Silver membership. Remind them that reaching 100 points will elevate them to Gold VIP status with enhanced perks.

if: session.project.loyalty_points >= 50
Congratulate the customer on earning enough rewards for a free handcrafted drink (50 points). Ask if they would like to redeem 50 points now. When they agree, call @tool.redeem_loyalty_reward.

if: session.project.loyalty_points < 50
Inform the customer that every $1 spent earns 1 loyalty point, and a free drink unlocks at 50 points. Remind them how many points they need to reach their next reward.
