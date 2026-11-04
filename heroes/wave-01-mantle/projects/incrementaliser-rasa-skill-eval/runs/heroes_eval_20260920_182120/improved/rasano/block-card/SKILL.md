---
name: block-card
description: Block or freeze a bank card. Activate for lost, stolen, fraud, damaged,
  expired, or travel-related card blocks.
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: block_card
  rasa_display_name: Block Card
---

# Block Card

## Instructions

Block the customer's card. Security first. Do not invent card numbers; use only numbers returned by tools.

## Identify the reason

Ask why they need to block the card. Valid reasons: lost, stolen, fraud,
damaged, expired, traveling, moving. Set `block_reason` via `set_fields`.
Done when `block_reason` holds one of the valid reasons.

## Pick the card

Once the reason is collected, invoke `@block.pick_card`:

:::ordered_block id=pick_card
steps:
  - id: fetch_cards
    execute_tool: list_cards
  - id: select_card
    instructions: |
      Show the customer's cards using the masked numbers from the tool result.
      Ask which card to block. Set selected_card_id to the full card number and
      selected_card_label to the masked form.
    complete_when: session.block_card.selected_card_id
:::

## Handle the reason

if: session.block_card.block_reason == "stolen" or session.block_card.block_reason == "fraud" or session.block_card.block_reason == "lost"
Explain that the card will be permanently blocked for protection.
Call block_card with the selected card. Advise contacting local
authorities if fraud or theft is involved. Offer a replacement card.
Done when block_card has been called and the replacement offered.

if: session.block_card.block_reason == "traveling" or session.block_card.block_reason == "moving"
Explain this can be a temporary block. Call block_card.
Mention they can ask later to order a replacement if needed.
Done when block_card has been called.

if: session.block_card.block_reason == "damaged" or session.block_card.block_reason == "expired"
Call block_card, then offer to order a replacement.
If they agree, ask shipping preference (standard or express), set
`shipping_type`, and call order_replacement_card.
Done when block_card has been called and, if accepted, order_replacement_card has been called with `shipping_type` set.

## Close

Confirm what was done in one or two short sentences suitable for voice.

## Examples

- Customer: My card was stolen.
