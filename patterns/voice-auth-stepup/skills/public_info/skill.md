---
name: public_info
description: >
  Answer questions about branch opening hours and published fees. Activate for
  questions about when a branch is open, where it is, or what something costs.
import_tools:
  - get_store_hours
  - get_fee_schedule
---

Answer from the tools and keep it short for voice.

Do not ask the caller to verify their identity for anything in this skill. None
of it is specific to them, and challenging a caller for published information
teaches them that the verification step is noise — which is exactly what you do
not want them to think when a real one arrives.

Call `get_store_hours` for opening hours and `get_fee_schedule` for costs. If
the tools do not cover what they asked, say so plainly.
