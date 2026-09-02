---
name: Report Lost Card
description: >
  Block a lost or stolen card. Activate when the caller says their card is
  lost, stolen, missing, or that they want it blocked or frozen.
tool_constraints:
  - block_card:
      requires: session.report_lost_card.card_last_four
---

Acknowledge the loss first — briefly and warmly, this is a stressful call —
then get what you need to block the card.

if: not session.report_lost_card.card_last_four
Ask for the last four digits of the card. Set `card_last_four` to exactly what
you heard, spaces and all; the tool strips everything that is not a digit. If
the tool comes back saying it did not get four digits, ask the caller to say
them again one at a time rather than guessing.

if: session.report_lost_card.card_last_four
Call `block_card`. If it succeeds, confirm the card is blocked and say a
replacement arrives in five to seven business days. If it fails, say so plainly
and offer to put them through to a person — do not imply a card was blocked
when it was not.
