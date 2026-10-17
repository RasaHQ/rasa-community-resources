---
name: authenticate
description: >
  Verify the developer's identity with their badge code before sensitive
  actions. Activate when authentication is required or when they ask to
  verify identity.
import_tools:
  - load_developer_profile
tool_constraints:
  - verify_badge:
      requires: session.authenticate.badge_attempt
---

Verify the developer before continuing with ticket changes or orders.

If developer details are missing, call load_developer_profile.

Ask for their four-digit badge code. Store what they say in badge_attempt.
Demo badge is four zero two one.

Call verify_badge with that code.

If authentication succeeds, confirm briefly and stop — parent skills will resume.
If it fails, allow one retry, then offer @skill.escalation.
