---
name: Request a Change
description: Build a market-card change or inspect the intentionally bad version using the protected factory gate.
import_tools:
  - mcp/factory:run_factory
---

Understand the participant's request from natural phrasing, not an exact phrase match.
For a request to show at most three currencies, call run_factory(request="good").
For a request to try the version that ignores the limit, call
run_factory(request="ignores-limit"). These are the only two supported request kinds.
If the request is unrelated or unclear, ask a short clarifying question instead of
calling the tool. Never supply paths, code, model names, modes or credentials.
Call the tool exactly once per request. If it returns an error or NOT_READY, report
that and do not automatically retry. The visible reply quotes the validated tool result; model prose is not a verdict.
Only the tool's protected gate result can
establish ACCEPT or REJECT. Include the actual verdict, failing test if any,
attempt fingerprint (computed by the tool), builder_calls, seconds and mode.
The runtime may use a LIVE OpenAI Agents API builder for good, normally about one
to two minutes and up to about 1.50 USD per build as an estimate, not a cap.
The ignores-limit request always uses the supplied SCRIPTED bad attempt with
zero builder calls. Nothing is deployed, applied, or released by this tool.
