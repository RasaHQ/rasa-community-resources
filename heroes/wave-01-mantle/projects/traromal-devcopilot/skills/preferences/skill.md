---
name: preferences
description: >
  View or change the developer's personal preferences for timezone, response
  length, Slack channel, and notification level. Activate when they say
  remember, prefer, set my default, what do you remember, or forget a
  preference.
---

Manage preferences explicitly and transparently.

For a view request, call get_preferences immediately.
For a change request, identify the preference and value, then call set_preference.
For a forget request, call clear_preference.

Never store passwords, badge codes, API keys, tokens, or other secrets.
Confirm the new value briefly after a successful tool result.
