# Atlas — Voice Travel Agent with Rasa Skills

```text
Author:        Rod Rivera
Assessed on:   2026-08-13
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev5, Python 3.11+, uv
Audience:      Practitioners building voice agents with Rasa Skills
Time:          60–90 minutes
```

Flagship companion repository for the tutorial
**[Build a Voice AI Agent with Rasa Skills](https://rasa.community/library/tutorials/voice-ai-agent/)**.

Atlas is a production-style **voice travel assistant** for Horizon Travel, built
with the Rasa **Skills** architecture and **Deepgram** for speech-to-text and
text-to-speech.

This repository is designed to be useful in two ways:

1. **Run the finished agent immediately**
2. **Build it yourself step by step** using the paste-ready files under
   [`tutorial/snippets/`](tutorial/snippets/) and the hosted tutorial on
   [rasa.community](https://rasa.community/library/tutorials/voice-ai-agent/)

> **Demo traveler:** Maya Chen (id `456`, PIN `4242`)
> A seeded SQLite travel environment is included under `data/source/`.

---

## What Atlas can do

| Skill | Capability |
| --- | --- |
| `trip_faq` | Answer common travel questions from references |
| `check_itinerary` | List upcoming bookings |
| `flight_status` | Look up delays, gates, and cancellations |
| `report_baggage` | File a lost-baggage report (progressive-control showcase) |
| `authenticate` | Verify identity with a voice PIN |
| `find_booking` | Select a booking (reusable sub-skill) |
| `change_booking` | Cancel or request changes (composition + confirmation) |
| `human_handoff` | Connect to a human agent |
| `intro` / `goodbye` | Orient and close the conversation |

---

## Quick start

```bash
make install
make env          # creates .env from .env.example — then fill in the three keys
make verify       # pre-flight: keys, project, data, connectivity
make train
make inspect      # voice + text via Rasa Inspector (Deepgram)
```

Required secrets in `.env`:

| Variable | Purpose |
| --- | --- |
| `RASA_LICENSE` | Rasa Pro Developer Edition license |
| `OPENAI_API_KEY` | LLM for routing + conversation |
| `DEEPGRAM_API_KEY` | Speech-to-text **and** text-to-speech |

---

## Architecture

```text
                         ┌─────────────────────┐
                         │       Traveler      │
                         │   voice or text     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Rasa Inspector     │
                         │ Deepgram ASR / TTS  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Rasa Maestro     │
                         │ skill selection     │
                         │ memory + control    │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
             ┌────────────┐  ┌────────────┐  ┌─────────────┐
             │   Skills   │  │   Tools    │  │ Travel FAQ  │
             │            │  │ travel.py  │  │ references  │
             └────────────┘  └─────┬──────┘  └─────────────┘
                                   │
                                   ▼
                            ┌────────────┐
                            │ SQLite demo│
                            │ data/source│
                            └────────────┘
```

---

## Progressive control

Not every part of an agent should be controlled the same way. Atlas uses focused
skills with explicit control where the business needs guarantees:

| Control | Defined in | Purpose |
| --- | --- | --- |
| `tool_constraints.requires` | Skill frontmatter | Hide a tool until a memory condition is true |
| `tool_constraints.requires_confirmation` | Skill frontmatter | Require explicit approval before a side effect |
| `if:` paragraphs | Skill body | Include instructions only when the condition matches |
| `utter:` | Skill frontmatter | Trigger an exact predefined response |
| `responses.yml` | Project / skill | Store deterministic response wording |
| `:::ordered_block` | Skill body | Require steps to execute in a strict sequence |
| `@skill.<name>` | Skill body | Compose another skill as a sub-flow |

```text
LLM discretion
      │
      ▼
conditional instructions
      │
      ▼
conditional tool access
      │
      ▼
explicit confirmation
      │
      ▼
ordered execution
      │
      ▼
exact deterministic wording
```

The **report baggage** skill is the showcase that combines recording notices,
ordered collection, confirmation, and verbatim success text.

---

## Project layout

| Path | Purpose |
| --- | --- |
| `agent.yml` | Identity, persona (Atlas), voice flags, rules |
| `integrations.yml` | OpenAI `gpt-5.2` + Inspector Deepgram ASR/TTS |
| `endpoints.yml` | Response rephraser and optional platform services |
| `memory.yml` | Project-wide session memory |
| `responses.yml` | Project-wide verbatim responses |
| `skills/` | One folder per skill (`skill.md`, optional local `tools.py`) |
| `tools/travel.py` | Shared tools only (`load_customer_profile`, `list_bookings`) |
| `lib/database.py` | SQLite demo backend |
| `data/source/` | JSON seed data for Maya’s trips |
| `scripts/verify_setup.py` | Pre-flight diagnostics |
| `tutorial/snippets/` | Paste-ready chapter checkpoints |

Pin: `rasa-pro==3.19.0.dev5`. New empty projects: `rasa init --engine maestro`.

This is a **Skills / Maestro** project. Do **not** add CALM v1 files
(`config.yml`, `domain.yml`, flow YAMLs under `data/`).

**Tool placement:** skill-owned tools live in `skills/<name>/tools.py` and are
auto-discovered. Only helpers used by multiple skills belong under `tools/`
and must be listed in `import_tools`.

---

## Demo data

```bash
make show-demo-data
```

Useful utterances:

- “What trips do I have?”
- “Is my Lisbon flight on time? Booking H T one two three four five”
- “I need to cancel a booking”
- “My bag did not arrive”
- “How much cabin baggage can I take?”

Reset the SQLite demo DB with `make reset-db`.

---

## Tutorial

The full didactic walkthrough lives on the community site:

**https://rasa.community/library/tutorials/voice-ai-agent/**

Local paste sets:

```bash
make tutorial
```

Recovery tags: see [`tutorial/TAGS.md`](tutorial/TAGS.md).

---

## Coding agents

See [`AGENTS.md`](AGENTS.md) and [`.cursor/rules/rasa-skills.mdc`](.cursor/rules/rasa-skills.mdc).

Always start with `make verify` before changing skills or tools.
