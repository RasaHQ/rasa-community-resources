# Rasa Skills project: Orchard Works IT helpdesk (Claude Sonnet 5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`internal-it-helpdesk`. Orchard Works is a fictional company.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider, no reasoning setting, prompt caching on the system
message. Channels: `rest`, `socketio`, `inspector`. The case's target channel
is Slack; it runs in web chat until Slack app credentials exist.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the Claude model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `hooks.py`, `lib/turn_order.py`: the turn-order request fix for Claude
- `memory.yml`: project memory, written by `load_session_employee` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `access_request` (with the
  confirmation gate on `grant_access`), `ticket_status`, `identity_recovery`
- `tools/orchard_helpdesk.py`: `load_session_employee`,
  `check_ticket_status`, `route_access_owner`, `route_identity_desk`
- `lib/helpdesk.py`: directory, approvals, tickets, the least-authority guard
  and the fictional-organisation allowlist, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard and hook tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/helpdesk.py` and decides at intake and again at
  the change, from the records then. The model supplies the employee's words
  for a role, a colleague's name if one was mentioned, and a `ticket_ref`
  copied from a tool result; never an employee id, a fact, an approval or an
  outcome.
- Only `grant_access` changes access, only for the signed-in employee, only
  the role on an owner-approved ticket, and it counts any other change in
  its before/after diff. Never add a path that grants temporary, broader or
  substitute access, or accepts a manager's endorsement as approval.
- Skill memory (`selected_ticket_ref`, `selected_scope_label`) is written
  only by `open_access_ticket`, only for an owner-approved ticket. Mantle
  renders at most 100 characters of a memory value; `tests/test_guard.py`
  checks every fixture role.
- The fixture's organisation must be exactly the casebook contract's,
  marked `(fictional)`, with its own systems and `.example` addresses;
  `lib/helpdesk.py` refuses to import otherwise.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- Leave `utter_on_user_denial` unset on the gate, so a correction made at the
  confirmation question is answered in the same turn.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
