---
name: manage_store_inventory
description: >
  Monitor store inventory levels, check stock thresholds for coffee beans, dairy, syrups, or bakery items.
  Activate when a customer, barista, or operator asks about store inventory, bean stock, or ingredient availability.
import_tools:
  - check_store_inventory
---

Assist customers and store operators with real-time inventory oversight.

If a store location was mentioned (e.g. Astoria store #3, Lower Manhattan store #5, Hell's Kitchen store #8), pass store_id=3 for Astoria, store_id=5 for Lower Manhattan, or store_id=8 for Hell's Kitchen. Otherwise, use store 5 by default.
If checking stock for coffee beans, beans, or any bean ingredient, always map category to exactly "Beans" when calling @tool.check_store_inventory.
If the operator asks about low stock or depleted items, call @tool.check_store_inventory with low_stock_only=True.
Otherwise, call @tool.check_store_inventory to list current on-hand quantities.

When reviewing the inventory results:
- Highlight any ingredients currently flagged with "low_stock" or "out_of_stock".
- If the operator wants to log a delivered shipment or restock supplies, invoke @skill.restock_inventory.
- If an essential ingredient is critically depleted (zero stock) and cannot fulfill orders, invoke @skill.escalate_supply_outage.
