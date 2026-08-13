---
name: Block Card
description: >
  Block or freeze a bank card that is lost, stolen, damaged, expired, or
  temporarily unused while traveling. Activate for card block, freeze, lost
  card, stolen card, or fraud on a card.
tool_constraints:
  - block_card:
      requires: session.block_card.selected_card_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_block_card
        utter_on_user_denial: utter_block_cancelled
      on_success: utter_card_blocked
  - order_replacement_card:
      requires: session.block_card.card_blocked
utter:
  - utter_recording_notice:
      on: activate
  - utter_stolen_warning:
      when: session.block_card.block_reason == "stolen"
  - utter_fraud_warning:
      when: session.block_card.block_reason == "fraud"
---

Help the customer block a card. Security first. Do not invent card numbers.

## Identify the reason

Ask why they need to block the card. Valid reasons: lost, stolen, fraud,
damaged, expired, traveling, moving. Set `block_reason` via `set_fields`.

Once the reason is collected, invoke `@block.pick_card`

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

## Handle reason

if: session.block_card.block_reason == "stolen" or session.block_card.block_reason == "fraud" or session.block_card.block_reason == "lost"
Explain that the card will be permanently blocked for protection.
Call block_card with the selected card. Advise contacting local
authorities if fraud or theft is involved. Offer a replacement card.

if: session.block_card.block_reason == "traveling" or session.block_card.block_reason == "moving"
Explain this can be a temporary block. Call block_card.
Mention they can ask later to order a replacement if needed.

if: session.block_card.block_reason == "damaged" or session.block_card.block_reason == "expired"
Call block_card, then offer to order a replacement.
If they agree, ask shipping preference (standard or express), set
`shipping_type`, and call order_replacement_card.

## Close

Confirm what was done in one or two short sentences suitable for voice.
