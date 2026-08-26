# Rasa Mantle Voice Banking Skills

```text
Author:        Rod Rivera
Assessed on:   2026-08-26
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev1, Python 3.11+, uv
Audience:      Practitioners building voice banking agents with Rasa Skills
Time:          75–90 minutes
```

Build a **voice** retail banking agent with the new Rasa **Skills / Mantle**
architecture and **Deepgram** for speech-to-text and text-to-speech.

We call our agent Rasano.

This repo is both:

1. A **finished working agent** you can run immediately
2. A **live-session tutorial** (`tutorial/TUTORIAL.md`) with paste-ready snippets

It replaces the older CALM-flows retail banking starter with Skills, progressive
control, and end-to-end voice.

## What Rasano can do

| Skill | Capability |
|---|---|
| `check_balance` | Look up account balances |
| `transfer_money` | Send money (composes `add_payee` when needed) |
| `list_payees` / `add_payee` / `remove_payee` | Manage authorised payees |
| `block_card` | Block lost/stolen/damaged cards + replacement |
| `banking_faq` | Answer common banking questions from references |
| `human_handoff` | Create a live-agent ticket |
| `goodbye` / `intro` | Orient and close the conversation |

Demo customer: **John Smith** (seeded SQLite bank under `data/source/`).

## Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/)
- Rasa Pro Developer Edition license (`RASA_LICENSE`)
- OpenAI API key (`OPENAI_API_KEY`)
- Deepgram API key (`DEEPGRAM_API_KEY`) for ASR **and** TTS

## Quick start

```bash
make install     # install dependencies with uv
make env         # create .env from .env.example
# edit .env and set RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY

make verify      # pre-flight: keys, project, demo data, connectivity
make train
make inspect
```

`make verify` is the single command to run whenever anything looks wrong. It
checks your Python version, license expiry, API keys, project validity, demo
data, and live connectivity to OpenAI and Deepgram, and tells you the exact fix
for anything it finds.

`make inspect` opens the Inspector. Use the microphone for voice (Deepgram) or type as a fallback.

## Project layout

```text
agent.yml              # Rasano persona + voice flags
integrations.yml       # OpenAI + Inspector (Deepgram ASR/TTS)
memory.yml             # project-wide memory
responses.yml          # greeting override
skills/                # one folder per skill (skill-local tools.py lives here)
tools/                 # shared @tool functions (used by 2+ skills)
lib/                   # SQLite demo bank helpers
data/source/           # seed JSON
tutorial/              # live session script + snippets
```

## Live tutorial

- Audience guide: [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md)
- Paste sets: [`tutorial/snippets/`](tutorial/snippets/)

Teaching spine: scaffold → FAQ prose → first tool → tool constraints →
block-card progressive control → transfer composition → voice demo.

## Progressive control (quick map)

| Lever | Where | What it guarantees |
|---|---|---|
| `tool_constraints.requires` | skill frontmatter | Tool hidden until memory condition is true |
| `requires_confirmation` | skill frontmatter | Explicit user approval before side effects |
| `if:` paragraphs | skill body | Only matching branch stays in the LLM prompt |
| `utter:` + `responses.yml` | frontmatter + YAML | Exact wording (compliance / warnings) |
| `:::ordered_block` | skill body | Strict step order when sequence is the requirement |

## Makefile

Run `make` with no arguments for the full grouped help screen.

| Target | Action |
|---|---|
| `make install` | Install dependencies (`uv sync --prerelease=allow`) |
| `make env` | Create `.env` from `.env.example` (never overwrites) |
| `make verify` | Full pre-flight diagnostics — start here if stuck |
| `make validate` | Fast skill / memory / tool validation only |
| `make train` | Validate + package the agent |
| `make inspect` | Open Inspector (voice + text) |
| `make run` | Start the API server |
| `make show-demo-data` | Print John Smith's accounts, cards, payees |
| `make reset-db` | Reseed the demo bank from `data/source/` |
| `make tutorial` | Show the live-session chapters and snippet paths |
| `make clean` | Remove models / caches / local db |
| `make clean-all` | Also remove `.venv` (full reset) |

## Notes for Rasa 3.20.0.dev1

- Package: `rasa-pro==3.20.0.dev1` (pre-release; `uv` prereleases enabled)
- Scaffold a fresh Mantle project with `rasa init --engine mantle`
  (there is no `--template voice`)
- LLM is `gpt-5.2`; do not set `temperature` (GPT-5 reasoning models only
  accept the default)
- Tools import from `rasa.mantle.tools` (not classic `rasa_sdk` Action classes)
- **Local-first tools:** a single-skill tool lives in `skills/<name>/tools.py`
  and is auto-discovered; only tools shared by 2+ skills go in `tools/*.py` and
  are pulled in with `import_tools`
- Tools are named in **plain prose** (`Call list_accounts`), never `@tool.name`
- Identity is loaded deterministically at session start: the project overrides
  `default_session_start` to `execute_tool`-run `load_customer_profile`
- Channels live in `integrations.yml` (no `credentials.yml` for Mantle projects)
- Inspector uses Deepgram by default when configured under `channels.inspector`

## License

Use with a valid Rasa Pro Developer Edition license. Review the
[Developer Terms](https://rasa.com/developer-terms).
