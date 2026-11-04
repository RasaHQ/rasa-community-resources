---
name: process_store_orders
description: >
  Manage barista store order queue, verify custom recipe modifications,
  and execute structured drink preparation workflows.
  Activate when a barista or store operator asks for the store order queue,
  incoming orders, or needs to process drink preparation for pickup.
import_tools:
  - fetch_store_order_queue
  - update_order_pickup_status
---

Assist the barista with store order queue management and drink preparation.

When a barista requests incoming orders or wants to start preparing drinks for a store, invoke @block.barista_fulfillment_flow.

:::ordered_block id=barista_fulfillment_flow
steps:
  - id: fetch_queue
    execute_tool: fetch_store_order_queue
  - id: select_order
    instructions: |
      Present the open orders from the queue tool result (Order ID, customer, item, size, milk type).
      Ask which order they want to prepare, and record the Order ID in selected_order_id.
    complete_when: session.process_store_orders.selected_order_id
  - id: verify_recipe
    instructions: |
      Verify drink specifications: cup size, dairy/plant milk selection, and any special preparation instructions.
      Confirm recipe checks with the barista and set recipe_verified to true.
    complete_when: session.process_store_orders.recipe_verified == True
  - id: start_brewing
    instructions: |
      Call @tool.update_order_pickup_status with selected_order_id and new_status "brewing".
      Confirm that brewing has begun.
    complete_when: session.process_store_orders.brewing_confirmed == True
  - id: mark_ready_for_pickup
    instructions: |
      When the barista finishes crafting the drink, call @tool.update_order_pickup_status with selected_order_id and new_status "ready_for_pickup".
      Confirm that the customer pickup notification has been dispatched.
    complete_when: session.process_store_orders.pickup_notified == True
:::

After completing the preparation workflow, ask the barista if they would like to pull the next order from the queue or inspect store inventory.
