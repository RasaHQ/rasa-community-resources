---
name: mantle-upgrade-and-debug
description: >
  Diagnose Rasa Mantle failures and perform version upgrades. Use when an
  install/lock/validate/train fails, when imports break after a version bump,
  when the agent ignores configuration, or when deciding which rasa-pro
  version to pin.
---

# Upgrades and the failure→cause map

Most Mantle failures report a symptom far from their cause. Look the message
up here BEFORE debugging from first principles.

## The failure→cause map

| You see | Actual cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: rasa.mantle` (or nothing importable) after pinning "latest stable" | The engine ships **only on `3.20.0.dev*`**; stable releases contain no engine package | Pin `rasa-pro==3.20.0.dev6`, `[tool.uv] prerelease = "allow"` |
| `ModuleNotFoundError: rasa.calm_v2` after an upgrade | Package renamed `rasa.calm_v2` → `rasa.mantle` at 3.20.0.dev1, no alias | Route all engine imports through a `lib/engine.py` try/except shim |
| `uv lock`: "versions that are not supported by your dependencies (e.g., rasa-pro==3.20.0.dev6 only supports >=3.11, <3.15)" | `requires-python` floor below 3.11 — the error never says "Python" | Set `requires-python = ">=3.11,<3.13"` |
| validate: `'provider': Extra inputs are not permitted` | Inline LLM config under `llm:` — removed in dev6 (`extra="forbid"`) | `llm: {model_group: <id>}` + a `model_groups:` entry |
| validate: `'model_group': Field required` | `llm:` block exists but names no group | Same as above |
| validate rejects root `memory.yml` | `llm_settable: true` on project-level memory | Move the field to `skills/<id>/memory.yml`, or have a tool write it |
| Agent ignores its rules/name/references; no error anywhere | Prompt-tuning keys nested under `agent:` — parsed then silently discarded | Move them to the top level of agent.yml |
| A skill branch never fires; no error | `if:` is indented — it's prose, not a condition | Move `if:` to column 0 of the skill body |
| Literal `@memory.foo` or `session.x.y` text in replies | Token not substitutable: `@memory` needs exactly 3 parts; `session.*` never substitutes in prose | Use `@memory.<ns>.<entry>`, keep `session.*` in `if:`/constraints |
| Unexpanded `${SOME_KEY}` at train time | Key missing from environment and `.env` | Add to `.env` (and to `.env.example` + `required-secrets` so the next person finds it) |
| `rasa init --engine <retired-name>` rejected | The pre-Mantle brand was retired; CLI accepts `{calm,mantle}` | Use `mantle`; purge the old name from docs — a stale brand in a runnable command is a broken command. (The name is not written out here so this file passes the very lint that catches it.) |

## Upgrading the pin (e.g. dev6 → dev7)

1. **Verify the target ships the engine before touching anything.** The
   authority is the published wheel's module list, not release notes: check
   that the wheel contains `rasa/mantle/`. If you can't check, upgrade one
   throwaway venv first and `python -c "import rasa.mantle"`.
2. Bump `rasa-pro==<target>` in pyproject.toml, run
   `uv lock` / `uv sync --prerelease=allow`.
3. **Sweep the prose too**: README "Verified with:", version mentions in
   docs. Do it with care — a careless sweep rewrites upgrade-path lines into
   `X → X` nonsense (this exact defect shipped in a real migration).
4. Re-derive the top-level agent.yml key list from the installed engine —
   dev releases add keys (`tool_timeout` arrived in dev6 unannounced). If
   the engine's agent-spec payload reads a key your tooling doesn't know,
   update the tooling's list.
5. Run the full ladder and say which rungs you ran:
   `lint_mantle.py` (offline consistency) → `rasa validate` → `rasa train`.
   **A green offline lint does NOT test the engine contract** — only an
   installed engine does. Never report "upgrade verified" off the lint alone.

## Debugging discipline (earned the hard way)

Before asserting any diagnosis, name the one cheap command that would prove
it wrong and run it — `git log --format=%cI`, a `grep` of the committed file,
one import in a venv. Most wrong turns in real Mantle debugging sessions came
from acting on the first plausible reading of a symptom; every one would have
been caught by a single command run before concluding.
