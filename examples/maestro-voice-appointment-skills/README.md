# Schedora — Voice Appointment Booking with Rasa Maestro

A production-style **voice appointment-booking agent** for a medical clinic, built with the new Rasa **Skills / Maestro** architecture and **Deepgram** for speech-to-text and text-to-speech.

Schedora books appointments, manages the patient's saved contacts, answers clinic questions, and hands conversations off to the clinic team — all through voice or text.

This repository is designed to be useful in two ways:

1. **Run the finished agent immediately**
2. **Build it yourself step by step**, using `make tutorial` and the paste-ready snippets in `tutorial/snippets/`

> **Demo patient:** Jamie Chen
> A seeded SQLite clinic environment is included under `data/source/`, so you can explore the complete agent without connecting to a real practice management system.

---

## What Schedora can do

| Skill              | Capability                                                            |
| ------------------ | --------------------------------------------------------------------- |
| `book_appointment` | Find open slots, confirm one, and write it to the clinic diary        |
| `list_contacts`    | Read back the patient's saved contacts                                |
| `add_contact`      | Save a new contact from a name and handle                             |
| `remove_contact`   | Remove a saved contact                                                |
| `clinic_faq`       | Answer clinic questions from reference material                       |
| `human_handoff`    | Raise a callback ticket for the clinic team                           |
| `intro`            | Introduce Schedora and orient the patient                             |
| `goodbye`          | Close the conversation gracefully                                     |

Before any of those run, `default_session_start` loads Jamie Chen's clinic profile into memory and greets the patient, so no skill has to open with a lookup.

`book_appointment` also demonstrates **skill composition**: if the patient wants to save their doctor to their contact list and no handle is on file, Schedora invokes the `add_contact` capability mid-journey and then returns to finish the booking.

---

## Why this project exists

Schedora is a compact example of how to build agents that combine **LLM flexibility with deterministic controls**.

Instead of placing an entire scheduling assistant inside one large prompt, the agent is decomposed into focused **skills** with explicit control over:

* which tools are available
* when tools become available
* when user confirmation is mandatory
* which instructions enter the model context
* which steps must happen in a strict order
* which responses must use exact wording

Booking is a good subject for this, because "find me a time" is an open-ended conversation while "write this appointment to the diary" is a side effect that must never happen by accident.

---

## Architecture

```text
                         ┌─────────────────────┐
                         │       Patient       │
                         │   voice or text     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Rasa Inspector     │
                         │                     │
                         │ Deepgram ASR / TTS  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Rasa Maestro     │
                         │                     │
                         │ skill selection     │
                         │ memory + control    │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
             ┌────────────┐  ┌────────────┐  ┌─────────────┐
             │   Skills   │  │   Tools    │  │  Clinic FAQ │
             │            │  │  shared +  │  │  references │
             │ booking    │  │ skill-local│  │             │
             │ contacts   │  └──────┬─────┘  └─────────────┘
             │ handoff    │         │
             └────────────┘         ▼
                             ┌──────────────┐
                             │ SQLite demo  │
                             │    clinic    │
                             │  + slot gen  │
                             └──────────────┘
```

---

# Quick start

## 1. Prerequisites

You need:

* **Python 3.10 to 3.13**
* [`uv`](https://docs.astral.sh/uv/)
* a Rasa Pro Developer Edition license
* an OpenAI API key
* a Deepgram API key

The following environment variables are required:

```bash
RASA_LICENSE=
OPENAI_API_KEY=
DEEPGRAM_API_KEY=
```

The same Deepgram API key is used for both **ASR** and **TTS**.

---

## 2. Install

```bash
git clone <this-repository>
cd <repository-directory>

make install
make env
```

`make env` creates `.env` from `.env.example` and **never overwrites an existing file**.

Add your credentials:

```bash
RASA_LICENSE=...
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...
```

---

## 3. Verify everything

```bash
make verify
```

Start here whenever something does not work.

The verifier checks:

* supported Python version
* Rasa license presence and expiry
* OpenAI credentials
* Deepgram credentials
* Rasa project validity
* skill definitions
* memory configuration
* tool layout — shared versus skill-local, and no tool sharing a skill's name
* that no `skill.md` still uses the non-existent `@tool.` reference
* seeded demo data
* the appointment slot generator
* live connectivity to OpenAI
* live connectivity to Deepgram

When possible, it tells you **exactly what is wrong and how to fix it**.

---

## 4. Train

```bash
make train
```

This validates the project and packages the agent.

---

## 5. Talk to Schedora

```bash
make inspect
```

Rasa Inspector will open in your browser.

Use the **microphone** to speak with Schedora through Deepgram, or type messages when you want a text fallback.

Try:

> I need to see a doctor next week.

> I need an urgent appointment with Doctor Patel.

> Who is on my contact list?

> Save Mary's number under @MaryLu.

> What is your cancellation policy?

> Can someone from the clinic call me back?

---

# Demo environment

Schedora ships with a small local clinic environment backed by SQLite.

The seeded patient is:

```text
Jamie Chen
```

with two saved contacts, **Joe (@JoeMyers)** and **Mary (@MaryLu)**.

Inspect the demo contacts, booked appointments, and the next open slots with:

```bash
make show-demo-data
```

If you modify the data while testing and want to return to the original state:

```bash
make reset-db
```

That deletes `data/schedora.db`, which is rebuilt from `data/source/` on the next tool call.

The source fixtures live under:

```text
data/source/
```

No external practice management API is required.

---

# Appointment slots

Slots are generated in `lib/appointments.py` rather than stored, so the demo never runs out of availability and never needs its fixtures refreshed.

The rules are the clinic's:

* weekdays only
* 08:00 to 18:00
* 30 minutes per appointment
* at most 10 options per search
* the preferred doctor shifts which times come back, so two doctors never look like they share one diary

Generation is **deterministic** — the same search returns the same slots, which matters when you are recording a demo or replaying one on stage. Slot strings use a canonical `DD/MM/YYYY HH:MM` form, and every tool result also carries a spoken form such as `Tuesday 11 August at 9:30 AM` so nothing reads a raw timestamp out loud.

---

# Project structure

```text
.
├── agent.yml
├── integrations.yml
├── endpoints.yml
├── memory.yml
├── responses.yml
│
├── skills/
│   ├── default_session_start/
│   ├── intro/
│   ├── book_appointment/
│   │   └── tools.py
│   ├── list_contacts/
│   ├── add_contact/
│   │   └── tools.py
│   ├── remove_contact/
│   │   └── tools.py
│   ├── clinic_faq/
│   ├── human_handoff/
│   │   └── tools.py
│   └── goodbye/
│
├── tools/
│   └── clinic.py
│
├── lib/
│   ├── database.py
│   ├── appointments.py
│   └── tool_helpers.py
│
├── data/
│   └── source/
│
└── tutorial/
    └── snippets/
```

### `agent.yml`

Defines the Schedora persona and agent-level configuration, including voice-related behaviour.

### `integrations.yml`

Configures external integrations including:

* OpenAI
* Rasa Inspector
* Deepgram speech-to-text
* Deepgram text-to-speech

Maestro projects use `integrations.yml`; there is no classic `credentials.yml` in this project.

### `endpoints.yml`

Platform services that `rasa train` and `rasa inspect` read: the contextual response rephraser used for the greeting, and the model groups it draws on. This file is part of a Maestro project — it is not a CALM v1 leftover.

### `memory.yml`

Defines project-wide memory available across skills — the patient's name, patient number, email, and phone.

### `responses.yml`

Contains deterministic response templates, including wording that should not be freely generated by the model.

### `skills/`

One directory per Maestro skill. Each skill encapsulates the instructions and controls for a specific capability, and — where it has tools nobody else uses — the Python for those too.

`skills/default_session_start/` overrides Rasa's bundled conversation opener. It is engine-managed rather than LLM-routed, so before the patient's first word it loads their clinic profile and then speaks the greeting.

### `tools/`

The **shared** Python functions, exposed with Rasa's `@tool` interface and pulled into a skill with `import_tools`. Only two tools qualify: `load_customer_profile` and `get_contacts`.

### `lib/`

Helpers for the local SQLite clinic, for appointment slot generation, and for reading and writing tool memory.

### `data/source/`

Seed data used to initialise the demo clinic.

### `tutorial/`

Paste-ready snippets for teaching or rebuilding the agent from scratch. Run `make tutorial` for the chapter list.

---

# Tools are local first

A tool that only one skill uses lives with that skill, in `skills/<name>/tools.py`. Rasa auto-discovers it, so there is nothing to declare — and listing it in `import_tools` is an error, because `import_tools` is the allowlist for the shared `tools/` folder only.

A tool is promoted to `tools/clinic.py` when a second skill genuinely needs it. Here, exactly two are:

| Tool | Home | Used by |
| ---- | ---- | ------- |
| `load_customer_profile`        | `tools/clinic.py`                      | session start, plus recovery in `book_appointment` |
| `get_contacts`                 | `tools/clinic.py`                      | `list_contacts`, `add_contact`, `remove_contact`   |
| `save_contact`                 | `skills/add_contact/tools.py`          | `add_contact`                                      |
| `delete_contact`               | `skills/remove_contact/tools.py`       | `remove_contact`                                   |
| `query_available_slots`        | `skills/book_appointment/tools.py`     | `book_appointment`                                 |
| `confirm_appointment_booking`  | `skills/book_appointment/tools.py`     | `book_appointment`                                 |
| `create_handoff_ticket`        | `skills/human_handoff/tools.py`        | `human_handoff`                                    |

The payoff is that a skill folder is the whole skill. Delete `skills/human_handoff/` and nothing else in the project changes.

**No tool shares a name with a skill.** Skills are named for what the patient wants (`list_contacts`, `add_contact`, `book_appointment`); tools are named for what the code does (`get_contacts`, `save_contact`, `confirm_appointment_booking`). Without that split, an instruction like "call `list_contacts`" could mean the tool or the skill, and Rasa's validator warns about exactly this ambiguity.

Skills ask for tools in **plain prose** — "Call `get_contacts` and read the names clearly." There is no `@tool.` reference in Maestro; only `@skill.<id>` and `@block.<id>` are real. `make verify` fails the build if a `skill.md` still uses `@tool.`.

---

# Progressive control

One of the main ideas demonstrated by this repository is that **not every part of an agent should be controlled in the same way**.

Rasa lets you progressively increase determinism where the application requires it.

| Control                     | Defined in        | Purpose                                                |
| --------------------------- | ----------------- | ------------------------------------------------------ |
| `tool_constraints.requires` | Skill frontmatter | Hide a tool until a memory condition becomes true      |
| `requires_confirmation`     | Skill frontmatter | Require explicit user approval before a side effect    |
| `if:` paragraphs            | Skill body        | Include instructions only when their condition matches |
| `utter:`                    | Skill frontmatter | Trigger an exact predefined response                   |
| `responses.yml`             | Project config    | Store deterministic response wording                   |
| `:::ordered_block`          | Skill body        | Require steps to execute in a strict sequence          |

The result is a spectrum of control:

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

Use the least restrictive mechanism that still guarantees the behaviour your application requires.

---

# Example: a booking that cannot happen by accident

Booking is a useful example because different parts of the journey need different levels of control.

Schedora may converse naturally while understanding:

> "Any chance of something with Doctor Patel on Thursday morning?"

But the system still enforces that:

1. the reason for the visit is captured before the diary is searched
2. only slots a tool returned are ever offered
3. the chosen day, time, and doctor are read back to the patient
4. the patient explicitly confirms
5. only then is the appointment written to the clinic diary

The language stays flexible while the **business invariant stays deterministic**. `query_available_slots` is hidden until `visit_reason` is set, and `confirm_appointment_booking` is hidden until the patient has confirmed.

---

# Skill composition

Skills do not need to become monolithic just because a patient journey spans multiple capabilities.

```text
book_appointment
      │
      ├── booking confirmed ──────────► done
      │
      └── "save my doctor to my contacts"
              │
              ▼
          add_contact
              │
              ▼
        back to booking
```

This lets capabilities remain independently understandable and reusable while Maestro coordinates them into a larger patient journey.

---

# Voice stack

Schedora uses **Deepgram** for both sides of the voice interaction:

```text
Microphone
    │
    ▼
Deepgram ASR
    │
    ▼
Rasa Maestro
    │
    ▼
Deepgram TTS
    │
    ▼
Speaker
```

Voice is configured through the Inspector channel in `integrations.yml`.

If you do not want to use voice while developing, Inspector also supports typed conversations.

Voice shapes the design throughout this project: responses are one or two sentences, dates and times are spoken in words rather than digits, handles are read back letter by letter before they are saved, and a search that returns ten slots offers two or three out loud instead of reciting the list.

---

# Build it yourself

Run:

```bash
make tutorial
```

for the chapter list. The build sequence is:

| Chapter | Concept                     | What you add                                       |
| ------- | --------------------------- | -------------------------------------------------- |
| 0       | Scaffold                    | `agent.yml`, `memory.yml`, `responses.yml`, `intro` |
| 1       | First skill, prose only     | `clinic_faq` with references                        |
| 2       | First shared tool           | `list_contacts`, `tools/clinic.py`, session start   |
| 3       | First local tool + guarantee| `remove_contact` with constraints and confirmation  |
| 4       | Showcase                    | `book_appointment` with ordered blocks and scopes   |
| 5       | Composition                 | `add_contact` invoked from the booking journey      |
| 6       | Remaining skills            | `goodbye`, `human_handoff`                          |
| 7       | Voice pass                  | `make inspect` with Deepgram                        |
| 8       | Flywheel close              | `make show-demo-data`                               |

Snippets live under `tutorial/snippets/` and mirror the finished agent, so you can paste them or diff against what you have.

---

# Make targets

Run:

```bash
make
```

to see the complete grouped help screen.

| Command               | What it does                                            |
| --------------------- | ------------------------------------------------------- |
| `make install`        | Install dependencies with `uv sync --prerelease=allow`  |
| `make env`            | Create `.env` from `.env.example` without overwriting   |
| `make verify`         | Run full pre-flight diagnostics                         |
| `make validate`       | Validate skills, memory, and tools                      |
| `make train`          | Validate and package the agent                          |
| `make inspect`        | Start Inspector with voice + text                       |
| `make run`            | Start the Rasa API server                               |
| `make show-demo-data` | Display Jamie's contacts, appointments, and open slots  |
| `make reset-db`       | Reset the SQLite clinic from seed data                  |
| `make tutorial`       | Show tutorial chapters and snippet paths                |
| `make clean`          | Remove generated models, caches, and local database     |
| `make clean-all`      | Also remove `.venv` for a complete reset                |

---

# Troubleshooting

## Start with `make verify`

For almost every setup problem:

```bash
make verify
```

The project deliberately centralises environment diagnostics here so you do not have to debug several tools independently.

### Rasa license errors

Confirm that `.env` contains:

```bash
RASA_LICENSE=...
```

Then run `make verify` — the verifier also checks the license expiry date.

### OpenAI errors

Confirm that `OPENAI_API_KEY=...` is present and valid. `make verify` performs a live connectivity check.

### Deepgram voice is not working

Confirm that `DEEPGRAM_API_KEY=...` is configured. The same key is used by Inspector for speech recognition and speech synthesis.

You can continue testing Schedora through text while diagnosing voice configuration.

### No appointment slots are offered

The clinic only opens on weekdays between 08:00 and 18:00, so a search that lands entirely on a weekend correctly returns nothing. Check the clock on your machine, then widen the date range.

### Demo data looks wrong

Reset it, then inspect it:

```bash
make reset-db
make show-demo-data
```

### Something is deeply broken

Perform a full local reset:

```bash
make clean-all
make install
make verify
make train
```

---

# Rasa version

This repository currently targets:

```text
rasa-pro==3.19.0.dev3
```

on `gpt-5.2`, configured in `integrations.yml` and `endpoints.yml`.

This is a **pre-release** version, so installation uses:

```bash
uv sync --prerelease=allow
```

A few implementation details are specific to the Maestro architecture used by this release:

* tools import from `rasa.calm_v2.tools`
* tools use Rasa's `@tool` interface rather than classic `rasa_sdk` Action classes
* tools are auto-discovered from `skills/<name>/tools.py` and, when shared, declared with `import_tools` from `tools/`
* skills call tools in prose; `@skill.` and `@block.` are the only reference forms
* `default_session_start` can be overridden to run work before the first turn
* channels are configured in `integrations.yml`
* Inspector can configure Deepgram ASR and TTS directly

If you are comparing this repository with older Rasa projects, expect the structure to look different. There are no CALM v1 files here — no `domain.yml`, no `config.yml`, and no flow YAML. `endpoints.yml` does remain: Maestro reads it for the response rephraser and model groups.

---

# Development workflow

For normal development:

```bash
make validate
make train
make inspect
```

Before opening a pull request:

```bash
make verify
```

If you change the demo clinic and need a clean test environment:

```bash
make reset-db
```

---

# Design principles

Schedora intentionally follows a few principles that transfer well beyond clinic scheduling.

### Keep skills small

A skill should represent a coherent capability, not the entire assistant.

### Keep business logic in tools

Skills describe behaviour and orchestration. Python tools perform application operations, and they live next to the skill that uses them until a second skill needs them.

### Make side effects explicit

Writing an appointment or deleting a contact deserves stronger controls than reading a list back.

### Prefer deterministic guarantees over prompt wishes

If something **must** happen, encode that requirement structurally instead of merely asking the model to remember it.

### Design for the ear, not the eye

Everything the agent says is spoken aloud. Short turns, spoken dates, and partial lists are design requirements, not polish.

### Make the repository runnable

Examples are much more useful when developers can execute them, inspect the state, break them, reset them, and try again.

---

# Suggested public repository name

```text
rasa-maestro-voice-appointment-skills
```

---

# Important

Schedora is a **demonstration application**.

The included SQLite clinic, patient record, contacts, appointments, and handoff tickets are simulated and are not suitable for handling real patient data.

Schedora does not give medical advice, and it is not a triage system. A production healthcare implementation would require additional controls around identity verification, consent, clinical safety, auditability, privacy and health-data regulation, retention, observability, resilience, and integration with an authorised practice management system.

---

# License

Use this project with a valid Rasa Pro Developer Edition license.

Review the [Rasa Developer Terms](https://rasa.com/developer-terms).
