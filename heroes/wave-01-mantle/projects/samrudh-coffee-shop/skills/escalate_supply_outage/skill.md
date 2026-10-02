---
name: escalate_supply_outage
description: >
  Trigger an urgent supply outage alert to regional management when an essential item
  (such as espresso beans or oat milk) is completely depleted at a store.
  Activate when an operator reports a severe stockout or emergency supply depletion.
import_tools:
  - escalate_outage_alert
---

Handle critical stock depletion and emergency supplier alerting.

Confirm the store location and the depleted ingredient name.

Call @tool.escalate_outage_alert with the store ID and depleted item name.

Report that the emergency supply notification has been routed to regional operations (regional_ops@artisanroastcoffee.com), an expedited transfer ticket has been opened, and the item has been marked out-of-stock on the digital POS.
