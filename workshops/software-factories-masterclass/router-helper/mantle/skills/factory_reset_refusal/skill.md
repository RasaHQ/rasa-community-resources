---
name: Factory reset refusal
description: >
  The customer asks for a factory reset of the router, in any wording ("factory
  reset", "reset to factory settings", "wipe the router"), at any point in the
  conversation, including as the answer to the question whether they mean a
  restart or a factory reset.
utter:
  - utter_factory_reset_refused:
      on: activate
---

The refusal has already been said word for word. Add nothing about a factory reset. Do
not give steps for one, not even steps the customer could follow themselves, and do not
offer to start one. Do not say you cannot help. If the customer then asks for a restart,
the restart skill handles it.
