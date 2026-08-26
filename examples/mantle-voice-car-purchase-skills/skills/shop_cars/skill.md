---
name: Shop Cars
description: >
  Check whether a specific car is in stock, suggest comparable alternatives, and
  say which dealers hold it. Activate when the customer asks if you have a
  model, where they can see it, or what else is like it.
import_tools:
  - check_availability
  - find_similar_cars
  - list_dealers
---

Help the customer shop a specific car. This skill is read-only — it never
reserves anything.

Ask which model they are interested in and set `model_of_interest` via
`set_fields`. Then call `@tool.check_availability`.

if: session.shop_cars.car_available == True
Say it is in stock. Give the price and the dealer. If more than one dealer has
it, call `@tool.list_dealers` with the model and read out at most two options.
Offer to reserve it for them.

if: session.shop_cars.car_available == False
Say plainly that it is not in stock right now. Call `@tool.find_similar_cars`
and offer two comparable cars with their prices. Ask if either interests them.

Keep every answer to a couple of short spoken sentences.
Never quote a price, dealer, or availability that did not come from a tool.
