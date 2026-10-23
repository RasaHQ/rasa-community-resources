# Rasa Mantle project — agent context

This directory is a **Rasa Mantle** agent (currently beta).
Mantle is Rasa's LLM-native engine: you describe behaviour in natural language
(`agent.yml`, skills) instead of hand-authoring intents, stories, and rules.

## Project layout

- `agent.yml` — the agent definition: an `agent:` block (`language`, `persona`)
  plus global `rules`.
- `integrations.yml` — LLM provider config and enabled channels (REST, Inspector).
- `skills/<name>/skill.md` — one skill per directory: YAML frontmatter (`name`,
  `description`) plus natural-language instructions. The starter project ships
  `view_transactions` (prose with `if:` scopes and a gated lookup tool) as a
  demo with mock tools.
- `skills/<name>/tools.py` — optional Python tools a skill can call, defined with
  the `@tool` decorator from `rasa.mantle.tools`.
- `skills/<name>/memory.yml` — optional skill-scoped memory fields (e.g. the
  selected account id used to gate lookup tools).
- `.env` — secret values (license key, API keys). Never commit this file.

## Build loop

Run these from the project directory, with the project's virtualenv on PATH:

```
rasa train             # validate and build a model into models/
rasa inspect           # open the Inspector UI to chat with the agent
```

Re-run `rasa train` after editing `agent.yml`, `integrations.yml`, or any skill.

## Where skills guidance lives

Coding-agent skills for building Mantle projects are installed under
`.claude/skills/` (Claude Code) and `.cursor/skills/` (Cursor). Read them before
adding or changing skills.

## Ground rules

- Reference secrets only as `${ENV_VAR}` (e.g. `${OPENAI_API_KEY}`); never inline
  raw keys into YAML.
- Do **not** create CALM v1 files here — no `domain.yml`, no `config.yml`, no
  `data/` NLU files. Mantle (`mantle`) does not use them.
- Keep each skill focused on one job; add a new `skills/<name>/` directory rather
  than overloading an existing skill.

Docs: https://github.com/RasaHQ/mantle-docs
