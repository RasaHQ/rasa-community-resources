---
name: Session Start
description: Load the customer profile before greeting. Activate at session start.
routing:
  engine_managed: true
import_tools:
  - load_customer_profile
---

Call load_customer_profile. Greet @memory.project.customer_name.
