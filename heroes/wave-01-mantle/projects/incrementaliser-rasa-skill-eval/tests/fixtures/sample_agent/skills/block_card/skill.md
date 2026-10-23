---
name: Block Card
description: Block a lost or stolen card. Activate for lost card or fraud.
tool_constraints:
  - block_card:
      requires: session.block_card.selected_card_id
      requires_confirmation:
        enabled: true
---

Help the customer block a card.

Invoke @block.pick_card then call block_card.

:::ordered_block id=pick_card
steps:
  - id: fetch
    execute_tool: list_cards
  - id: END
:::
