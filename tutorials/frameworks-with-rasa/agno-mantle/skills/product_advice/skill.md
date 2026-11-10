---
name: product_advice
description: Expose the existing Agno adviser for public synthetic Willow Shop product advice.
---

Call ask_product_adviser with the user's product question. Application code
resolves the demo profile and conversation from the channel sender. The tool
has no user ID or session ID argument. Do not ask the user to put those IDs
inside their question.

Explain a ready result's product and explanation. The existing adviser uses
its registered product tool, configured model and stored preferences. These
are seeded fictional preferences, not actual customer records.

If the sender is unknown, explain that this exercise needs one of the public
demo sender names from its README. If advice is unavailable, offer to retry.
Do not say an order was placed, a payment was made or a profile was changed.
