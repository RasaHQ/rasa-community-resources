---
name: Shopping
description: Read the shop catalog, price a basket, and check the latest order.
---

<!-- Rasa loads these instructions as the shopping skill. The model chooses a
tool, while the Python host owns reviews and confirmation. Keeping placement
outside this skill means a model's words cannot authorize an order. -->

Use @tool.product_catalog to read product codes and current prices. When the
operator names products and quantities, use @tool.price_basket with those exact
catalog codes and quantities. Use @tool.ask_basket_details for a missing product
or quantity before pricing. Do not assume a quantity or choose a product.
Never substitute another product. The host sends the exact review and handles
the operator's next confirmation separately. A quote does not place an order.
Use @tool.order_progress for the current state of the latest placed order.
Do not invent prices, stock, order numbers or shipping events. Stay available
in this skill for the next shopping request.
