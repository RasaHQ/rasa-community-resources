---
name: place_customer_order
description: >
  Place a customized coffee, tea, or bakery order for store pickup with explicit customer confirmation.
  Activate when the customer wants to order coffee, buy a drink, purchase a pastry, or place an order.
import_tools:
  - place_coffee_order
  - check_order_status
memory:
  selected_item:
    type: string
    description: "Chosen beverage or bakery item name."
  item_name:
    type: string
    description: "Chosen beverage or bakery item name."
  selected_size:
    type: string
    description: "Cup size (Small, Regular, Large)."
  size:
    type: string
    description: "Cup size (Small, Regular, Large)."
  selected_milk:
    type: string
    description: "Milk selection (Whole Milk, Oat Milk, Almond Milk, None)."
  milk_type:
    type: string
    description: "Milk selection (Whole Milk, Oat Milk, Almond Milk, None)."
  store_id:
    type: integer
    description: "Chosen store pickup location ID (3 for Astoria, 5 for Lower Manhattan, 8 for Hell's Kitchen)."
  selected_store:
    type: string
    description: "Chosen store location name or ID."
  order_completed:
    type: boolean
    description: "Set to True once the coffee/bakery order is successfully placed."
complete_when:
  condition: "session.place_customer_order.order_completed"
---

Help the customer place an order for pickup at Artisan Roast Coffee Co.

For single beverage/bakery orders, consecutive orders, or group orders:
1. Determine the item(s) to order. Ask what beverage or bakery item they want if completely unspecified.
2. For any unspecified options (size or milk choice), apply smart defaults (Size: Regular, Milk: Whole Milk, Store ID: 5 for Lower Manhattan or 3 for Astoria if specified).
3. Present the default order combination to the customer in a single turn for quick confirmation (e.g., "I can prepare a Regular Cappuccino with Whole Milk for pickup at Astoria #3. Shall I place this order?").
4. If ordering consecutive items or multiple items in a group order, process all items using this single-turn combination approach to minimize back-and-forth turns.
5. Call @tool.place_coffee_order with the item name, store ID, size, milk type, and quantity. Set order_completed to True.

<!-- 
================================================================================
RASA MANTLE TEAM FEEDBACK & ISSUE SUMMARY
================================================================================
ISSUE:
When running with LiteLLM and Google Gemini (e.g., gemini/gemini-2.5-flash), multi-turn tool execution occasionally fails with:
  litellm.BadRequestError: Vertex_ai_betaException BadRequestError - 400 INVALID_ARGUMENT
  "Please ensure that function call turn comes immediately after a user turn or after a function response turn."

ROOT CAUSE:
In Rasa Mantle's Orchestrator (`rasa.mantle.orchestration.orchestrator`), conversation history turns passed to LiteLLM can contain consecutive `assistant` role messages (e.g. an `assistant` turn with `tool_calls` followed by an `assistant` utterance or prompt) without an intervening `tool` role response turn. Google Gemini strictly rejects message histories that break the `user` -> `assistant (tool_calls)` -> `tool (response)` sequence.

EXPECTED BEHAVIOR:
1. Mantle's history formatter should normalize turn history before passing messages to LiteLLM/Gemini, ensuring any `assistant` turn containing `tool_calls` is immediately followed by a matching `tool` response turn.
2. If tool execution is gated or requires confirmation (`requires_confirmation: enabled`), Mantle should inject a synthetic `tool` response event (e.g., `content: "confirmation_pending"`) to preserve strict provider role ordering.
================================================================================
-->

When the order is confirmed:
- Read back the generated Order ID (e.g. ORD-504) character by character.
- Confirm the store pickup location and estimated prep time (approximately 5 minutes).
- Announce the loyalty points earned on this purchase.
