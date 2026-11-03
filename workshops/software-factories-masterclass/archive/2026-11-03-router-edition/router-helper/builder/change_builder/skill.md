---
name: Change builder
description: >
  The customer asks for a change to the router helper itself, for example
  "add a check that tells me the line status". Activate only for a request to
  change or extend the helper. Never for a router restart or a reset.
---

When the customer asks for a change to the helper, call @tool.build_change once with their request in one sentence.
The tool sends the customer a message with the build id, whether a file was saved, the file's path and its sha256.
Do not repeat or reword that message and do not invent any of those values. Do not apply the change to the helper.
If the tool says a build is already running, tell the customer to wait for it to finish.
