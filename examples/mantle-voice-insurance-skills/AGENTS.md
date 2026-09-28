# Rasa Mantle project — Poly voice insurance

This directory is a **Rasa Mantle** agent (Skills / `rasa.mantle`) that teaches
building a **voice** insurance assistant with **Deepgram** ASR + TTS.

## Layout

- `agent.yml` — identity, persona (Poly), voice flags, rules
- `integrations.yml` — OpenAI LLM (`gpt-5.2`) + Inspector Deepgram ASR/TTS
- `endpoints.yml` — NLG rephraser + model groups (same model family; no temperature)
- `memory.yml` — project-wide memory (`session.project.*`)
- `responses.yml` — project-wide verbatim responses (greeting override)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`, `references/`)
- `tools/` — shared `@tool` functions only (used by 2+ skills or session start)
- `lib/` — shared Python helpers (SQLite demo insurance DB)
- `data/source/` — JSON seed data for the demo customer
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
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs, `credentials.yml`)
- Keep `endpoints.yml` for NLG / model_groups — do **not** set `temperature` on GPT-5
- Local-first tools: single-skill tools in `skills/<id>/tools.py` (auto-discovered);
  only genuinely shared tools in `tools/*.py` with `import_tools`
- Reference tools in **plain prose** (`Call get_claim_status`). The `@` token is
  only for `@skill.<id>` and `@block.<id>` — there is **no** `@tool.` token
- Never name a tool the same as a skill (rename the tool; e.g. `get_claim_status`)
- Load fixed demo identity at session start via `skills/default_session_start`
  (`execute_tool: load_customer_profile` then `utter_greet`) — do not rely on the
  LLM to call a zero-arg tool on the first turn
- Declare every `context.memory.set(...)` key in skill or project `memory.yml`
- Prefer progressive control: prose → tool constraints → scoped `if:` →
  verbatim `utter:` → ordered blocks only when order is the requirement
- Boolean expressions in skill `if:` use Python `True`/`False`, not YAML
- Only put `description:` on llm_settable (or collect-owned) memory fields
- Makefile may `-include .env` for presence checks — never blanket-`export` it
- Voice instructions must be short sentences suitable for TTS

Docs for authors: see `tutorial/TUTORIAL.md` and `.cursor/rules/rasa-skills.mdc`
