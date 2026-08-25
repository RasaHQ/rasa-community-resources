# Rasa Skills project — Atlas voice travel

This directory is a **Rasa Skills / Maestro** agent that teaches building a
**voice** travel assistant with **Deepgram** ASR + TTS.

Pin: `rasa-pro==3.19.0.dev7`. LLM: `gpt-5.2`. Scaffold command for new
projects: `rasa init --engine maestro` (not `--template voice`).

## Layout

- `agent.yml` — identity, persona (Atlas), voice flags, rules
- `integrations.yml` — OpenAI LLM + Inspector channel with Deepgram ASR/TTS
- `endpoints.yml` — optional platform services (response rephraser, tracing)
- `memory.yml` — project-wide memory
- `responses.yml` — project-wide verbatim responses
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`, `references/`)
- `tools/` — **shared** `@tool` functions only (`import_tools` required)
- `lib/` — shared Python helpers (SQLite demo travel DB)
- `data/source/` — JSON seed data for the demo traveler
- `scripts/` — `verify_setup.py`, `validate_project.py`, `show_demo_data.py`
- `tutorial/` — paste-ready snippets for the hosted community tutorial

## Tool placement

- Default: put tools in `skills/<name>/tools.py` (auto-discovered; no
  `import_tools` entry).
- Shared (`tools/` at the agent root) only when **two or more skills** need
  the same function. This project shares `load_customer_profile` and
  `list_bookings`; everything else is skill-local.
- Imports:

```python
from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult
```

## Build loop

```bash
make install
make env
make verify
make validate
make train
make inspect
```

## Ground rules

- Skills live under `skills/<name>/` as `skill.md` files with optional
  `tools.py`, `references/`, `memory.yml`, and `responses.yml`
- Progressive control levers: `tool_constraints`, `requires`,
  `requires_confirmation`, `if:` markers, `utter:`, `:::ordered_block`,
  `@skill.<name>`
- Every condition is an expression string with fully namespaced memory
  (`session.flight_status.booking_ref`, `session.project.authenticated`), never
  a mapping. See `.cursor/rules/rasa-skills.mdc` for the full verified syntax
- Skill `memory.yml` uses a `schema:` root key and `text` (not `string`) types
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs)
- Reference secrets only as env vars / `.env` — never commit keys
- Voice instructions must be short sentences suitable for TTS
- After changing a skill, run `make validate`, then `make verify` and
  `make inspect`

Hosted tutorial: https://rasa.community/library/tutorials/voice-ai-agent/
