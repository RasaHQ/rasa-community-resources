# <PROJECT NAME> — a Rasa Mantle agent

This repository is a Rasa Mantle (Skills engine) project. The rules below are
not style preferences — each one encodes a failure mode that is silent or
misleadingly reported by the engine, verified against rasa-pro `3.20.0.dev6`.

## Version doctrine (read before touching pyproject.toml)

- The Mantle engine ships **only on the `3.20.0.dev` pre-release line**. The
  newest stable `rasa-pro` has **no engine package**. Never "upgrade to latest
  stable"; pin `rasa-pro==3.20.0.dev6` (or the current dev release) and keep
  `[tool.uv] prerelease = "allow"`.
- `requires-python = ">=3.11,<3.13"`. A lower floor fails `uv lock` with a
  resolver error that never mentions Python.
- Engine imports live in `lib/engine.py` and nowhere else. The engine package
  is `rasa.mantle` (renamed in 3.20.0.dev1 with no alias for the old name);
  routing every import through the shim makes the next rename a one-file change.

## Layout

```
agent.yml            # identity + persona; prompt-tuning keys at TOP LEVEL
integrations.yml     # llm -> model_group reference; model_groups; channels
memory.yml           # PROJECT memory: tool-written facts, never llm_settable
skills/<id>/skill.md # one skill per folder
skills/<id>/tools.py # tools only this skill uses
skills/<id>/memory.yml  # skill-scoped memory; llm_settable lives HERE
tools/               # shared tools, referenced via import_tools
lib/engine.py        # the only file that imports rasa.mantle directly
.env.example         # every credential the project reads, committed
.env                 # real credentials, gitignored, never committed
```

## The five silent traps (the lint enforces all of them)

1. **`name:`, `description:`, `rules:`, `references:`, `conversation:`,
   `before_end:`, `tool_timeout:` are SIBLINGS of `agent:` in agent.yml, never
   children.** Nested inside they parse without error and are discarded.
2. **`llm:` in integrations.yml is a model-group reference**
   (`llm: {model_group: <id>}`). Inline `provider`/`model`/`api_key` there is
   rejected since 3.20.0.dev6. Providers/credentials live on the
   `model_groups:` entry, with `api_key_env: SOME_ENV_VAR` — the *name* of the
   variable, unquoted, no `${...}`. `api_key_env: VAR` does not expand: `api_key`
   is on the engine's `SENSITIVE_DATA` list, so `read_yaml` returns it raw and
   the provider receives the literal characters `${VAR}` as its key.
3. **Root `memory.yml` may not contain `llm_settable: true`.** Project memory
   is written by tools. LLM-settable fields go in `skills/<id>/memory.yml`
   under `schema: public:`.
4. **In skill.md, `if:` only works at column 0** of the body. Indented `if:` is
   prose. Conditions use `session.<skill>.<field>` / `session.project.<field>`.
5. **In skill prose, only `@memory.<namespace>.<entry>` (exactly three parts)
   is substituted.** Raw `session.x.y` in prose reaches the LLM as dead text.

## Workflow

- Scaffold or extend with the `.claude/skills/mantle-*` skills — they carry the
  full templates and grammar.
- Gate before every commit: `python3 scripts/lint_mantle.py` (the pre-commit
  hook runs it for you — install once with `./hooks/install-hooks.sh`).
- The lint is offline and answers "internally consistent?". Only
  `uv sync` + `rasa validate`/train answers "does it actually run?" — a green
  lint is necessary, not sufficient. Say which one you ran.
- Never commit `.env`. Credentials resolve shell → project `.env`; put every
  needed key name in `.env.example` with an empty value.

## When something fails, check the map first

`.claude/skills/mantle-upgrade-and-debug/SKILL.md` has a failure→cause table
(`'provider': Extra inputs are not permitted`, resolver errors, import errors
after upgrades). Most Mantle failures report a symptom far from their cause;
look the message up before debugging from first principles.
