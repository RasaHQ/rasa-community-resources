---
name: mantle-new-project
description: >
  Scaffold a complete, working Rasa Mantle project from scratch. Use when the
  user wants a new Mantle/Rasa agent, a new bot project, or asks to "set up
  Rasa". Produces every file with the correct 3.20.0.dev6 shapes so the first
  validate passes.
---

# Scaffold a new Rasa Mantle project

Ask for (or infer): the agent's **domain**, a short **persona name**, and which
**channels** it needs (text-only vs voice). Then create every file below —
do not skip any; each absence is a lint finding or a runtime surprise.

## 1. pyproject.toml — the version facts are non-negotiable

```toml
[project]
name = "<project-slug>"
version = "0.1.0"
description = "<one line>"
readme = "README.md"
requires-python = ">=3.11,<3.13"
dependencies = [
    "rasa-pro==3.20.0.dev6",
    "python-dotenv>=1.0.0",
]

[tool.uv]
prerelease = "allow"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lib"]
```

WHY, so you can defend it: the Mantle engine ships **only on the
`3.20.0.dev` pre-release line** — the newest *stable* rasa-pro contains no
engine package at all, so "latest stable" produces a project whose imports
fail. `prerelease = "allow"` is what lets uv resolve a dev pin. The
`>=3.11` floor is required by 3.20; a lower floor fails `uv lock` with an
error about "versions not supported by your dependencies" that never
mentions Python.

If the project needs credentials beyond `RASA_LICENSE` and `OPENAI_API_KEY`
(e.g. `GEMINI_API_KEY`), also declare them:

```toml
[tool.rasa-catalog]
required-secrets = ["GEMINI_API_KEY"]
```

## 2. lib/engine.py — the only file that imports the engine directly

```python
"""Engine imports, resolved in one place.

Rasa renamed the engine package rasa.calm_v2 -> rasa.mantle in 3.20.0.dev1,
with no alias. Every tool imports from here, never from rasa.* directly.
"""
from __future__ import annotations

try:  # 3.20.0.dev1 and later
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult
    ENGINE_PACKAGE = "rasa.mantle"
except ImportError:  # 3.19.x and earlier
    from rasa.calm_v2.tools.decorator import ToolContext, tool
    from rasa.calm_v2.tools.result import ToolResult
    ENGINE_PACKAGE = "rasa.calm_v2"

__all__ = ["ENGINE_PACKAGE", "ToolContext", "ToolResult", "tool"]
```

Also create empty `lib/__init__.py` and `tools/__init__.py`.

## 3. agent.yml — prompt-tuning keys are TOP-LEVEL

```yaml
agent:
  id: <project-slug>
  language: en
  persona: |
    You are <Name>, a concise assistant for <domain>.
    Ask one question at a time and keep answers short.
    Never invent facts — always use tools for data.

# TOP-LEVEL keys, siblings of `agent:`. Nested inside they parse without
# error and are silently discarded — the engine reads them only from the top
# level of this file.
name: <Name>
description: <one line, shown to the model>

rules:
  - "Be polite, clear, and brief."
  - "Never state data that did not come from a tool."
  - "Activate a skill only when the request clearly matches it."
```

For a **voice** agent add, inside the `agent:` block:

```yaml
  voice:
    enabled: true
    asr: deepgram          # or a dotted path to a custom engine class
    tts: deepgram
```

## 4. integrations.yml — llm is a model-group reference

```yaml
# The orchestrator LLM is a model-group reference. Provider, model and
# credentials live on the named group, never inline under `llm:` — the
# inline form was removed in rasa-pro 3.20.0.dev6.
llm:
  model_group: orchestrator

model_groups:
  - id: orchestrator
    models:
      - provider: openai
        model: gpt-4.1-mini
        api_key: ${OPENAI_API_KEY}
        temperature: 0.0

channels:
  rest:
    enabled: true
  inspector:
    enabled: true
```

## 5. memory.yml — project memory is tool-written

```yaml
# Project memory — facts that outlive a single skill. Readable and writable
# by EVERY skill. Keep it to facts about the end user and the session.
# NEVER put `llm_settable: true` here — the engine rejects it at the project
# level. LLM-settable fields belong in skills/<id>/memory.yml.
authenticated:
  type: bool
  description: Whether the caller has proven their identity this session.
  initial_value: false
```

## 6. Skills — at least one real skill plus a greeting

Create `skills/<skill_id>/skill.md` using the **mantle-skill-authoring**
skill's grammar (frontmatter → prose → top-level `if:` branches). Put tools
only that skill uses in `skills/<skill_id>/tools.py`; shared tools in
`tools/` and reference them with `import_tools:` in the frontmatter.

## 7. Credentials and hygiene

- `.env.example` (committed): every key the project reads, values empty, one
  comment per key saying where to get it. Start with:

  ```bash
  # Rasa Pro licence (free Developer Edition, a long JWT, one line)
  RASA_LICENSE=
  # LLM for routing and conversation
  OPENAI_API_KEY=
  ```

- `.gitignore` must contain: `.env`, `.venv/`, `models/`, `__pycache__/`,
  `.rasa/`.

## 8. Makefile — the beginner's interface

```makefile
.DEFAULT_GOAL := help
.PHONY: help env install validate train chat lint clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'
env: ## Create .env from .env.example
	@test -f .env || cp .env.example .env
install: ## Install dependencies
	uv sync --prerelease=allow
lint: ## Offline consistency checks
	python3 scripts/lint_mantle.py
validate: lint ## Validate the project without training
	uv run rasa validate
train: ## Validate and train
	uv run rasa train
chat: ## Talk to the agent in the Inspector
	uv run rasa inspect
clean: ## Remove models and caches
	rm -rf models .rasa
```

## 9. Finish

1. Copy `scripts/lint_mantle.py` and `hooks/` from the starter pack if not
   present; run `./hooks/install-hooks.sh`.
2. Run `python3 scripts/lint_mantle.py` — must be clean before the first commit.
3. Tell the user exactly which of the two gates you ran: the offline lint
   (consistency) vs `make validate`/`train` (actually exercises the engine —
   needs `uv sync` and a `RASA_LICENSE`). A green lint alone is not "it works".
