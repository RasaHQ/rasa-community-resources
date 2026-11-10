---
name: Block Card
description: >
  Block a customer's lost or stolen card. Activate when the caller wants a card blocked.
tool_constraints:
  - block_card:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_block
---

Help the caller block one card.

Call `list_cards` first. If two cards could match what the caller said, ask which one they mean.
Never block a card until the caller has confirmed which one.
