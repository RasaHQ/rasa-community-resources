---
name: browse_coffee_menu
description: >
  Search the coffee, tea, chocolate, and bakery menu items and prices.
  Activate when the customer asks what drinks, teas, coffees, or pastries are on the menu,
  or asks about beverage prices.
import_tools:
  - search_coffee_menu
---

Help the customer explore the menu and discover our beverages and bakery items.

Ask what category or drink they are interested in if they did not specify.
Call @tool.search_coffee_menu with their requested category or search query.

When presenting items:
- State the item name, product type, and unit price clearly (e.g. Ethiopia Rg is $3.00, Oatmeal Scone is $3.00).
- Mention available sizes (Small, Regular, Large).
- Ask if they would like to place an order for pickup.
