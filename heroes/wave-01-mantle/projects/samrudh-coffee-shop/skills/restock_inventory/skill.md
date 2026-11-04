---
name: restock_inventory
description: >
  Record received inventory shipments and add stock quantities for beans, milk, syrups, or bakery items.
  Activate when the operator specifies an item to restock or adds stock quantities.
import_tools:
  - restock_store_inventory
---

Help the store operator record received inventory items.

Collect the store ID (3: Astoria, 5: Lower Manhattan, 8: Hell's Kitchen), item name, and the quantity added.

Call @tool.restock_store_inventory with the store ID, item name, and quantity added.

Once the tool confirms the update:
- State the new total stock level and unit of measure.
- Confirm whether the item is now safely above the reorder threshold.
- Ask if there are additional delivered items to log.
