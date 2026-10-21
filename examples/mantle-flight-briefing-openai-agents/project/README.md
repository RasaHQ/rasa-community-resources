# Mantle flight-briefing conversation — unqualified draft

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided
Verified with: rasa-pro 3.21.0.dev5 installation and source inspection only; conversation not verified
Audience: Maintainers qualifying the flight-briefing conversation
Time: not_provided

Read the [resource status and setup](../README.md) first. This project is not a
working end-to-end example yet: the installed pin lacks the documented dynamic
MCP hook metadata path. Its `ToolCallPayload` has no `metadata` field; the
preflight and MCP runtime do not forward it. Keep the server's identity refusal
intact until the owning engine supplies and qualifies the missing capability.

The lock points to the verified dev Core wheel in `../worker/inputs/`, not a
registry release. Source controls do not establish a Mantle conversation,
widget rendering, voice or a live Agents API result. No assessment date or
assessor is supplied until the intended workflow is qualified.

Environment variable names are listed in `.env.example`; values must remain
only in the facilitator's own runtime environment. No file is loaded by this
project to discover credentials.
