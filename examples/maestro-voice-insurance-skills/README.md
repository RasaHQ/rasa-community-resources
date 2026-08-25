# Poly — Voice Insurance with Rasa Maestro

```text
Author:        Rod Rivera
Assessed on:   2026-08-25
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev7, Python 3.11+, uv
Audience:      Practitioners building voice insurance agents with Rasa Skills
Time:          75–90 minutes
```

A production-style **voice insurance agent** built with Rasa **Skills / Maestro** (`calm_v2`) and **Deepgram** for speech-to-text (Flux) and text-to-speech (Aura).

Poly can file auto and homeowners claims, check claim status, view policies, answer insurance questions, schedule inspections, and hand conversations off to a human — through voice or text.

This repository is useful in two ways:

1. **Run the finished agent immediately**
2. **Build it yourself step by step** using [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md)

> **Demo customer:** Serena Williams (id `123`)  
> Seeded SQLite data lives under `data/source/`. Identity is loaded deterministically at session start — not by hoping the LLM calls a zero-arg tool.

---

## What Poly can do

| Skill | Capability |
| --- | --- |
| `default_session_start` | Load Serena’s profile, then greet (engine-managed) |
| `view_policies` | List policies with premium and coverage limit |
| `check_claim_status` | Look up claim progress (`get_claim_status` tool) |
| `schedule_inspection` | Book an inspection (`book_inspection` tool) |
| `file_claim` | File an auto or homeowners claim (progressive-control showcase) |
| `insurance_faq` | Answer common insurance questions from references |
| `human_handoff` | Create a ticket for a live insurance agent |
| `intro` | Orient the customer to capabilities |
| `goodbye` / `leave_feedback` | Close + quick rating |

---

## Quick start

```bash
make install
make env          # creates .env from .env.example — then fill in the three keys
make verify       # pre-flight: keys, project, demo data, connectivity
make train
make inspect      # voice + text via Rasa Inspector (Deepgram)
```

Required secrets in `.env` (never commit this file):

| Variable | Purpose |
| --- | --- |
| `RASA_LICENSE` | Rasa Pro Developer Edition license |
| `OPENAI_API_KEY` | LLM for routing + conversation (`gpt-5.2`) |
| `DEEPGRAM_API_KEY` | Speech-to-text **and** text-to-speech |

Run `make` alone for the full grouped help screen.

---

## Stack

- `rasa-pro==3.19.0.dev7` via `uv`, Python 3.10–3.13
- LLM: OpenAI `gpt-5.2` in `integrations.yml` and `endpoints.yml` — **no temperature**
- Voice: Deepgram Flux ASR + Aura TTS under `channels.inspector`
- Tools: local-first (`skills/<id>/tools.py`) + shared (`tools/insurance.py`)

---

## Progressive control

Instead of one giant prompt, Poly uses focused skills with explicit control over:

* which tools are available
* when tools become available (`tool_constraints.requires`)
* when user confirmation is mandatory
* which instructions enter the model context (`if:`)
* which steps must happen in a strict order (`:::ordered_block`)
* which responses must use exact wording (`utter:` / `responses.yml`)

The **file claim** skill is the showcase that combines those levers.

**Tool references in skill prose are plain names** (`Call get_claim_status`).  
`@` is only for `@skill.<id>` and `@block.<id>` — there is no `@tool.` token.

---

## Project layout

| Path | Purpose |
| --- | --- |
| `agent.yml` | Identity, persona (Poly), voice flags, rules |
| `integrations.yml` | OpenAI LLM + Inspector Deepgram ASR/TTS |
| `endpoints.yml` | NLG rephraser + model groups |
| `memory.yml` | Project-wide session memory |
| `responses.yml` | Project-wide verbatim responses |
| `skills/` | One folder per skill (optional local `tools.py`) |
| `tools/insurance.py` | Shared tools (`load_customer_profile`, `list_policies`) |
| `lib/database.py` | SQLite demo backend |
| `data/source/` | JSON seed data |
| `scripts/verify_setup.py` | Pre-flight diagnostics |
| `tutorial/` | Live-session guide + paste-ready snippets |

This is a **Maestro / Skills (`calm_v2`)** project. Do **not** add CALM v1 files
(`config.yml`, `domain.yml`, flow YAMLs, `credentials.yml`).

---

## Demo data

```bash
make show-demo-data
```

Useful utterances:

- “What policies do I have?”
- “Check the status of claim CLAIM1236”
- “I need to file a claim on my car”
- “Does my homeowners policy cover flood damage?”

Reset the SQLite demo DB with `make reset-db`.

---

## Build-with-me tutorial

See [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md) and [`tutorial/TAGS.md`](tutorial/TAGS.md).

```bash
make tutorial
```

---

## Make targets

| Target | Purpose |
| --- | --- |
| `make install` | `uv sync --prerelease=allow` |
| `make env` | Create `.env` from `.env.example` (never overwrites) |
| `make verify` | Full pre-flight diagnostics |
| `make validate` | Fast skill/memory/tool validation |
| `make train` | Package the agent model |
| `make inspect` | Voice + text Inspector |
| `make run` | API server on port 5005 |
| `make show-demo-data` | Print Serena’s policies and claims |
| `make reset-db` | Reseed `data/insurance.db` |
| `make tutorial` | Print chapter / snippet paths |
| `make clean` / `make clean-all` | Remove artefacts / also `.venv` |

---

## Coding agents

See [`AGENTS.md`](AGENTS.md) and [`.cursor/rules/rasa-skills.mdc`](.cursor/rules/rasa-skills.mdc).

Always start with `make verify` before changing skills or tools.
