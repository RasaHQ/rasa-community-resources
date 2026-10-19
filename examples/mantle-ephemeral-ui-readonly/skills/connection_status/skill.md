---
name: Connection status
description: Show the connection metadata the owner made visible to this device.
import_tools:
  - show_connection_status
---

When the user asks which connections are visible, call show_connection_status
once. Describe only its returned status. An unavailable result does not mean
there are no connections. Never ask for a token or account identifier. Do not
invoke provider operations, create grants or suggest another identity.
