# Rasa Skills project — DevPilot developer copilot

This directory is a **Rasa Skills / Mantle** agent that builds a
**developer voice copilot** (DevPilot) with **Deepgram** ASR + TTS.

Pin: `rasa-pro==3.20.0.dev6`. LLM: DeepSeek `deepseek-chat` via the
OpenAI-compatible endpoint `https://api.deepseek.com` (model group
`deepseek-llm` in `integrations.yml`). Scaffold command for new
projects: `rasa init --engine mantle` (not `--template voice`).

Windows note: the `rasa.exe` shim fails with "Failed to canonicalize script
path" — always use `uv run python -m rasa ...` instead of `uv run rasa ...`.

## Layout

- `agent.yml` — identity, persona (DevPilot), voice flags, rules
- `integrations.yml` — DeepSeek LLM + Inspector channel with Deepgram ASR/TTS
- `endpoints.yml` — optional platform services (response rephraser, tracing)
- `memory.yml` — project-wide memory
- `responses.yml` — project-wide verbatim responses (greeting, fallback)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`)
- `tools/` — **shared** `@tool` functions only (`import_tools` required)
- `lib/` — shared Python helpers (SQLite demo dev DB)
- `data/source/` — JSON seed data for the demo developer
- `scripts/` — `verify_setup.py`, `validate_project.py`, `show_demo_data.py`

## Skills

- `intro`, `goodbye` — orientation and close
- `authenticate` — badge-code verification (`verify_badge`)
- `dispatch` — today's task queue + SLA summary (`list_jobs`)
- `find_job` — select one task; sub-skill (`get_job`)
- `job_status` — SLA/priority branching, urgency
- `job_close` — ordered-block task close with confirmation
- `parts_order` — hardware/license orders, restricted-item approval
- `ticket_notes` — tickets: list/update/reopen/comment/standup/briefing/file
- `escalation` — page the on-call engineer
- `deploy_gate` — deploys gated on open critical tickets (auth required)
- `pr_tracker` — reviews waiting on you + your PRs' CI state
- `reminders` — personal reminders
- `handoff` — end-of-shift on-call summary
- `safety_faq` — dev procedure questions (no RAG: DeepSeek has no embeddings
  endpoint, so the FAQ answers live in the skill instructions)

## Tool placement

- Default: put tools in `skills/<name>/tools.py` (auto-discovered; no
  `import_tools` entry).
- Shared (`tools/` at the agent root) only when **two or more skills** need
  the same function. This project shares `load_technician_profile` and
  `list_jobs`; everything else is skill-local.
- Imports:

```python
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
```

## Build loop

On macOS/Linux: `make install`, `make env`, `make verify`, `make validate`,
`make train`, `make inspect`.

On Windows (no make), use the equivalents:

```bash
uv sync --prerelease=allow
Copy-Item .env.example .env   # then fill in keys
uv run python scripts/verify_setup.py
uv run python scripts/validate_project.py
uv run python -m rasa train
uv run python -m rasa inspect
```

## Ground rules

- Skills live under `skills/<name>/` as `skill.md` files with optional
  `tools.py`, `memory.yml`, and `responses.yml`
- Progressive control levers: `tool_constraints`, `requires`,
  `requires_confirmation`, `if:` markers, `utter:`, `:::ordered_block`,
  `@skill.<name>`
- Every condition is an expression string with fully namespaced memory
  (`session.ticket_notes.summary_verified`, `session.project.authenticated`),
  never a mapping; avoid compound `or`/`and` conditions — use separate `if:`
  blocks
- Skill `memory.yml` uses a `schema:` root key and `text` (not `string`) types
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs)
- Reference secrets only as env vars / `.env` — never commit keys
- Voice instructions must be short sentences suitable for TTS
- After changing a skill, run `make validate`, then `make verify` and
  `make inspect`
- Demo data: developer Alex Chen (id `101`, badge `4021`); tasks DEV1001–1006,
  tickets TKT1001–1008, plus PR/deployment/reminder seeds. Teammates Priya
  Sharma (`102`) and Sam Okafor (`103`) exist for PR/handoff realism.
