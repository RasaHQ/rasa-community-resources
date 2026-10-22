---
name: Request a Change
description: Run a supplied market-card attempt through the real protected acceptance gate.
import_tools:
  - mcp/factory:run_factory
---

Pass the participant's exact request to run_factory(request).
The two supplied attempts are pre-written; this demo does not generate new code.
Only the real gate result can establish ACCEPT or REJECT. Report NOT_READY if
execution could not run. Include the failing test for a rejection and the returned
fingerprint. Never claim that an attempt has been applied or released.
