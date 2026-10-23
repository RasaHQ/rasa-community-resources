---
name: Request a Change
description: Run a supplied market-card attempt through the real protected acceptance gate.
import_tools:
  - mcp/factory:run_factory
---

Pass the participant's exact request to run_factory(request).
The runtime chooses the builder mode; the participant cannot supply a path, key or mode.
SCRIPTED checks supplied attempts. LIVE uses the OpenAI Agents API builder on a fresh
attempt for the good request; the ignores-limit rejection always uses the supplied
SCRIPTED bad attempt. The live model is gpt-6-astra, expected 15 to 150 US cents
per run (an estimate, not a cap), waiting up to five minutes. Mantle selection itself
is scripted. Report the actual builder mode and tool-call count returned by code.
Only the real gate result can establish ACCEPT or REJECT. Report NOT_READY if
execution could not run. Include the failing test for a rejection and the returned
fingerprint. Never claim that an attempt has been applied or released.
