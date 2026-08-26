# Rasa Mantle project — Telano voice telecom care

This directory is a **Rasa Mantle** agent (Skills / calm_v2) that teaches
building a **voice** telecom care assistant with **Deepgram** ASR + TTS.

## Layout

- `agent.yml` — identity, persona (Telano), voice flags, rules
- `integrations.yml` — OpenAI LLM (`gpt-5.2`) + Inspector Deepgram ASR/TTS
- `endpoints.yml` — thin platform file (NLG rephrase + model_groups only)
- `memory.yml` — project-wide memory (`session.project.*`)
- `responses.yml` — project-wide verbatim responses (greeting override)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`, `references/`)
- `skills/default_session_start/` — engine-managed opener: `execute_tool`
  `load_customer_profile` then `utter_greet`
- `tools/` — shared `@tool` functions only (2+ skills or session start)
- `lib/` — shared Python helpers (SQLite demo telco)
- `data/source/` — JSON seed data for the demo telco DB
- `scripts/` — `verify_setup.py` (pre-flight) and `show_demo_data.py`
- `tutorial/` — live-session script and paste-ready snippets

## Build loop

```bash
make install   # uv sync --prerelease=allow
make env       # copy .env.example -> .env, then fill in the keys
make verify    # pre-flight diagnostics (scripts/verify_setup.py)
make train
make inspect   # voice + text Inspector
```

Run `make` alone for the grouped help screen.

## Ground rules

- Reference secrets only as env vars / `.env` — never commit keys
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs)
- Keep a minimal `endpoints.yml` for platform services (NLG / model_groups);
  do **not** wire classic `action_endpoint` / `actions_module`
- Local-first tools: single-skill tools live in `skills/<id>/tools.py`
  (auto-discovered). Only shared tools go in `tools/*.py` with `import_tools`
- Reference tools in plain prose (`Call get_bill_summary`). The `@` token is
  only for `@skill.<id>` and `@block.<id>` — there is **no** `@tool.` token
- Do not name a tool the same as a skill (e.g. use `factory_reset_router`)
- Declare every `context.memory.set(...)` key in the owning skill or project
  `memory.yml`
- Prefer progressive control: prose → tool constraints → scoped `if:` →
  verbatim `utter:` → ordered blocks only when order is the requirement
- Boolean expressions in skill `if:` must use Python `True`/`False`
- Only put `description:` on llm_settable (or collect-owned) memory fields
- Voice instructions must be short sentences suitable for TTS
- Do not set `temperature` for GPT-5 models in YAML

Docs for authors: see `tutorial/TUTORIAL.md` and `.cursor/rules/rasa-skills.mdc`
