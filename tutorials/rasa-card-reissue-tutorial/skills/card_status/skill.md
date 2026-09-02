---
name: card_status
description: >
  Tell the caller which cards are on their account and what state each is in.
  Activate when the caller asks what cards they have, or about the status of a
  card, without asking for a replacement.
import_tools:
  - list_cards
---

Call `list_cards` and tell the caller what is on the account.

Identify each card by its product name and last four digits only. Never state a
full card number, expiry date, or security code — you do not have them and must
not invent them.

If the caller then asks for a replacement, go to @skill.card_reissue.
