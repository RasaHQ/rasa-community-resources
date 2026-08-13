---
name: authenticate
description: >
  Verify the traveler's identity with a voice PIN before sensitive changes.
  Activate when authentication is required or when they ask to verify identity.
import_tools:
  - load_customer_profile
  - verify_traveler_pin
tool_constraints:
  - verify_traveler_pin:
      requires: session.authenticate.pin_attempt
---

Verify the traveler before continuing with sensitive booking changes.

If customer details are missing, call @tool.load_customer_profile.

Ask for their four-digit Horizon Travel PIN. Store what they say in pin_attempt.
Demo PIN is four two four two.

Call @tool.verify_traveler_pin with that PIN.

If authentication succeeds, confirm briefly and stop — parent skills will resume.
If it fails, allow one retry, then offer @skill.human_handoff.
