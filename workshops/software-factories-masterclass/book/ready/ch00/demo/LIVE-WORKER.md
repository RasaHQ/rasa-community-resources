# Managed specialist worker


Use the [maintained example launcher](README.md): from the example directory,
run `make setup`, then `make run`. It owns the worker, authenticated MCP transport,
actual Mantle Inspector and shutdown. Do not combine the launcher with an older
two-shell backend or a manually staged development wheel.

The current `worker` installs Core and the OpenAI Python client for the Agents API from its committed
registry lock. `worker/core-artifact.json` records the exact published wheel and
hash; `worker/uv.lock` records its dependency closure. The separate Mantle project
has its own compatible SDK. Historical experiments in `live-worker/` are not the
current class runtime or a substitute for the final released finder pin.

With the facilitator's own OpenAI key, the specialist uses Core's native managed
session adapter. Without it, tool selection is explicitly SCRIPTED. Source
handlers, not model prose, supply the card values. Constructed `Replay DEMO101`
is available only when explicitly requested and remains labelled Replay.

Credentials stay in the facilitator's ignored example-root `.env` or process
environment; no key belongs in arguments, MCP metadata, URLs or logs. The
launcher refuses alternate provider base URLs and does not grant the hosted
specialist network access. Local public-source handlers retain their fixed-host,
cache, response-size and request-budget boundaries.

The service rejected `spend_control`, so the current native path omits it.
Call, event, deadline and timeout limits are execution bounds, not an enforced
per-session monetary cap. A stated expected cost is an estimate, not observed
billing. Follow the facilitator's recorded rehearsal budget and session limit.

Each native revision starts a fresh managed session with the prior validated
brief. Core's finite limits and the briefing revision fence remain required:
cancelling a Python thread is not hostile-process isolation. Failed or incomplete
native turns cannot become completed briefings. Sharing a private briefing
capability grants access; this does not establish engine-user binding.

Offline injected-source and SDK tests do not establish live model, provider,
voice, browser, fresh-clone or factory acceptance. The main README records the
current integration checkpoint and remaining consuming checks.
