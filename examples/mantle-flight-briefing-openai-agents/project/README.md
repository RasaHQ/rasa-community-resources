# Mantle flight-briefing conversation — unqualified draft

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided
Verified with: rasa-pro 3.21.0.dev5 actual hook loader/runner; full conversation not verified
Audience: Maintainers qualifying the flight-briefing conversation
Time: not_provided

Read the [resource status and setup](../README.md) first. This project uses the
approved capability-ID fallback: start returns a private `briefing_id`; get and
revise require it. A conversation without that ID is refused. A conversation
with the actual ID can access the briefing. There is no engine-sender binding,
listing operation, engine patch or fork. The skill keeps the ID in tool context
and must not disclose it in the user-facing reply.

The pinned engine reads `llm.model_group` from `integrations.yml`. Its current
public documentation's dynamic MCP metadata hook is absent from this pin and
from all nine newer published versions inspected through 3.21.0. That upstream
capability is a separate future contribution, not a prerequisite for this path.

The lock points to the verified dev Core wheel in `../worker/inputs/`, not a
registry release. Source controls do not establish a Mantle conversation,
widget rendering, voice or a live Agents API result. No assessment date or
assessor is supplied until the intended workflow is qualified.

Environment variable names are listed in `.env.example`; values must remain
only in the facilitator's own runtime environment. No file is loaded by this
project to discover credentials.
