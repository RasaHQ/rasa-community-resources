# Rasa Maestro project — Schedora voice appointment booking

This directory is a **Rasa Maestro** agent (Skills / calm_v2) that teaches
building a **voice** appointment-booking assistant for the Clinic of Rasa with
**Deepgram** ASR + TTS. It targets `rasa-pro==3.19.0.dev3` on `gpt-5.2`.

## Layout

- `agent.yml` — identity, persona (Schedora), voice flags, rules
- `integrations.yml` — OpenAI LLM + Inspector channel with Deepgram ASR/TTS
- `endpoints.yml` — platform services read by `rasa train` / `rasa inspect`
  (contextual response rephraser, model groups). Maestro still uses this file;
  it is not a CALM v1 leftover.
- `memory.yml` — project-wide memory (`session.project.*`)
- `responses.yml` — project-wide verbatim responses (greeting override)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `memory.yml`,
  `responses.yml`, `tools.py`, `references/`)
- `skills/default_session_start/` — override of the bundled opener: loads the
  patient profile, then greets
- `tools/clinic.py` — the only **shared** `@tool` functions, pulled in with
  `import_tools`
- `lib/` — shared Python helpers: `database.py` (SQLite demo clinic +
  `find_project_root()`), `appointments.py` (slot generation),
  `tool_helpers.py` (memory helpers)
- `data/source/` — JSON seed data for the demo clinic. Resolve paths with
  `find_project_root()` — tools run from the model snapshot, where
  `Path(__file__)` has no `data/source/`.
- `scripts/` — `verify_setup.py` (pre-flight) and `show_demo_data.py`
- `tutorial/` — paste-ready snippets per chapter

## Build loop

```bash
make install   # uv sync --prerelease=allow
make env       # copy .env.example -> .env, then fill in the keys
make verify    # pre-flight diagnostics (scripts/verify_setup.py)
make train
make inspect   # voice + text Inspector
```

Run `make` alone for the grouped help screen.

## Tools are local first

A tool used by exactly **one** skill lives in that skill's own
`skills/<id>/tools.py`. It is auto-discovered and must **not** appear in
`import_tools`. Only genuinely shared behaviour goes in `tools/clinic.py`:

| Tool | Home | Used by |
|---|---|---|
| `load_customer_profile` | `tools/clinic.py` | session start, plus recovery in `book_appointment` |
| `get_contacts` | `tools/clinic.py` | `list_contacts`, `add_contact`, `remove_contact` |
| `save_contact` | `skills/add_contact/tools.py` | `add_contact` |
| `delete_contact` | `skills/remove_contact/tools.py` | `remove_contact` |
| `query_available_slots` | `skills/book_appointment/tools.py` | `book_appointment` |
| `confirm_appointment_booking` | `skills/book_appointment/tools.py` | `book_appointment` |
| `create_handoff_ticket` | `skills/human_handoff/tools.py` | `human_handoff` |

**Never give a tool the same name as a skill.** `get_contacts` / `save_contact` /
`delete_contact` / `confirm_appointment_booking` exist because
`list_contacts` / `add_contact` / `remove_contact` / `book_appointment` are
skill ids, and prose like "call list_contacts" would be ambiguous — the
validator warns when prose names a skill id without the `@skill.` prefix.

Skill-local tool modules import from `lib/`, never from `tools/clinic.py`, so no
skill depends on another skill's tools.

## Session start

`skills/default_session_start/skill.md` overrides the bundled opener. It is
`routing.engine_managed: true`, imports `load_customer_profile`, and runs an
ordered block that executes that tool and then utters `utter_greet`. Jamie Chen
is loaded before the patient's first word, so **no other skill needs a "load the
profile first" paragraph**.

## Ground rules

- Reference secrets only as env vars / `.env` — never commit keys
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, `credentials.yml`,
  `data/nlu.yml`, flow YAMLs). `endpoints.yml` is **not** on that list.
- `@tool.<name>` is **not** a Maestro construct. Call tools in plain prose
  ("Call `get_contacts`"). Only `@skill.<id>` and `@block.<id>` are references.
- Tool names in `tool_constraints`, `execute_tool:`, and `on_success` must be
  the real Python function names
- Keep each skill focused; compose with `@skill.<name>` when needed
- Prefer progressive control: prose → tool constraints → scoped `if:` →
  verbatim `utter:` → ordered blocks only when order is the requirement
- Booleans in `if:` conditions use Python literals (`True` / `False`)
- In skill `memory.yml`, only `llm_settable: true` fields carry a `description`
- Never let the model invent appointment slots, contacts, or clinic policy —
  those come from tools and `references/`

## Demo data

The demo patient is **Jamie Chen**, seeded with contacts **Joe (@JoeMyers)** and
**Mary (@MaryLu)**. `make show-demo-data` prints the cheat sheet;
`make reset-db` deletes `data/schedora.db` so it reseeds from `data/source/`.

Docs for authors: see `.cursor/rules/rasa-skills.mdc`
