# Rasa Mantle project — Rasano voice banking

This directory is a **Rasa Mantle** agent (Skills / calm_v2) that teaches
building a **voice** retail banking assistant with **Deepgram** ASR + TTS.

## Layout

- `agent.yml` — identity, persona (Rasano), voice flags, rules
- `integrations.yml` — OpenAI LLM + Inspector channel with Deepgram ASR/TTS
- `memory.yml` — project-wide memory (`session.project.*`)
- `responses.yml` — project-wide verbatim responses (greeting override)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`, `references/`)
- `skills/default_session_start/` — override that `execute_tool`-loads the
  customer profile into project memory before greeting
- `tools/` — tools shared by 2+ skills (imported via `import_tools`);
  single-skill tools live in `skills/<name>/tools.py` (auto-discovered)
- `lib/` — shared Python helpers (SQLite demo bank)
- `data/source/` — JSON seed data for the demo bank
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
- Scaffold new projects with `rasa init --engine mantle` (no `--template voice`)
- LLM is `gpt-5.2`; never set `temperature` on it
- Name tools in plain prose (`Call check_balance`), never `@tool.name`
- Keep each skill focused; compose with `@skill.<name>` when needed
- Prefer progressive control: prose → tool constraints → scoped `if:` →
  verbatim `utter:` → ordered blocks only when order is the requirement

Docs for authors: see `tutorial/TUTORIAL.md` and `.cursor/rules/rasa-skills.mdc`
