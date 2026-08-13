# Telano — Voice Telecom Care with Rasa Maestro

```text
Author:        Rod Rivera
Assessed on:   2026-08-13
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev5, Python 3.11+, uv
Audience:      Practitioners building voice telecom care agents with Rasa Skills
Time:          75–90 minutes
```

A production-style **voice telecom care agent** built with the new Rasa **Skills / Maestro** architecture and **Deepgram** for speech-to-text and text-to-speech.

Telano can troubleshoot slow internet, guide router reboots, remotely factory-reset a router, explain bills, answer telecom FAQs, and hand conversations off to a human — all through voice or text.

This repository is designed to be useful in two ways:

1. **Run the finished agent immediately**
2. **Build it yourself step by step** using the live-session tutorial in [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md)

> **Demo customer:** Serena Williams (`customer_id` `123`)
> A seeded SQLite telecom environment is included under `data/source/`, so you can explore the complete agent without connecting to a real BSS/OSS system.

---

## What Telano can do

| Skill | Capability |
| --- | --- |
| `intro` | Orient the customer / explain capabilities |
| `default_session_start` | Load Serena Williams, then greet (engine-managed) |
| `telco_faq` | Answer common telecom questions from reference material |
| `check_bill` | Summarize a monthly bill and optionally list charges |
| `run_diagnostics` | Run a network speed test |
| `reboot_router` | Guide a customer through power-cycling their router |
| `reset_router` | Remotely factory-reset a registered router (showcase) |
| `internet_troubleshooting` | Compose diagnostics → reboot → reset for slow internet |
| `human_handoff` | Create a ticket for a live support agent |
| `goodbye` | Close the conversation and optionally collect feedback |

`internet_troubleshooting` demonstrates **skill composition**: it invokes
`@skill.run_diagnostics`, `@skill.reboot_router`, and `@skill.reset_router`
as needed.

---

## Why this project exists

Telano is a compact example of how to build agents that combine **LLM flexibility with deterministic controls**.

Instead of placing an entire telecom assistant inside one large prompt, the agent is decomposed into focused **skills** with explicit control over:

* which tools are available
* when tools become available
* when user confirmation is mandatory
* which instructions enter the model context
* which steps must happen in a strict order
* which responses must use exact wording

That makes this repository useful both as a telecom demo and as a reference for building more reliable agentic applications with Rasa.

---

## Architecture

```text
                         ┌─────────────────────┐
                         │       Customer      │
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
             │   Skills   │  │   Tools    │  │  Telco FAQ  │
             │            │  │            │  │ references  │
             │ internet   │  │ @tool funcs│  │             │
             │ billing    │  └──────┬─────┘  └─────────────┘
             │ reset      │         │
             └────────────┘         ▼
                             ┌──────────────┐
                             │ SQLite demo  │
                             │    telco     │
                             └──────────────┘
```

---

# Quick start

## 1. Prerequisites

You need:

* **Python 3.10–3.13**
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
* tool imports
* seeded demo data
* live connectivity to OpenAI
* live connectivity to Deepgram
* trained model presence and size (stub archives warn)

When possible, it tells you **exactly what is wrong and how to fix it**.

---

## 4. Train

```bash
make train
```

This validates the project and packages the agent.

---

## 5. Talk to Telano

```bash
make inspect
```

Rasa Inspector will open in your browser.

Use the **microphone** to speak with Telano through Deepgram, or type messages when you want a text fallback.

Try:

> My internet is slow.

> Can you explain my February bill?

> Please factory-reset my router.

> What is the difference between rebooting and resetting a router?

> I need to speak to a human.

---

# Demo environment

Telano ships with a small local telecom environment backed by SQLite.

The seeded customer is:

```text
Serena Williams
customer_id: 123
```

Inspect bills and routers with:

```bash
make show-demo-data
```

If you modify the data while testing and want to return to the original state:

```bash
make reset-db
```

The source fixtures live under:

```text
data/source/
```

No external telecom API is required.

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
│   ├── telco_faq/
│   ├── check_bill/
│   ├── run_diagnostics/
│   ├── reboot_router/
│   ├── reset_router/
│   ├── internet_troubleshooting/
│   ├── human_handoff/
│   └── goodbye/
│
├── tools/
│   └── telco.py
│
├── lib/
│   └── database.py
│
├── data/
│   └── source/
│
├── scripts/
│   ├── verify_setup.py
│   └── show_demo_data.py
│
└── tutorial/
    ├── TUTORIAL.md
    ├── TAGS.md
    └── snippets/
```

### `agent.yml`

Defines the Telano persona and agent-level configuration, including voice-related behaviour.

### `integrations.yml`

Configures external integrations including:

* OpenAI
* Rasa Inspector
* Deepgram speech-to-text
* Deepgram text-to-speech

### `endpoints.yml`

Optional platform services still loaded by Rasa (NLG rephraser, `model_groups`,
tracker/event broker stubs). LLM conversation routing and voice stay in
`integrations.yml`. Do not add classic `action_endpoint` here — tools use
calm_v2 `@tool` under `tools/`.

### `skills/`

One folder per skill. Each skill starts from `skill.md` and may include
`memory.yml`, `responses.yml`, `references/`, and local tools.

### `tools/`

Shared `@tool` functions used by **two or more skills** or by session start,
imported via `import_tools`. Single-skill tools live in `skills/<id>/tools.py`
and are auto-discovered (no `import_tools`).

### `lib/` + `data/source/`

SQLite helpers and JSON seed fixtures for the demo customer.

### `tutorial/`

Paste-first live-session materials. See `make tutorial`.

---

# Progressive control

Prefer structural guarantees over longer prose when the model misbehaves:

1. prose instructions
2. `tool_constraints.requires`
3. scoped `if:` paragraphs
4. verbatim `utter:` + `responses.yml`
5. `:::ordered_block` only when order is the requirement

The `reset_router` skill is the progressive-control showcase (remote factory
reset is irreversible for custom Wi-Fi settings).

---

# Live tutorial

Build the agent in a 75–90 minute session:

```bash
make tutorial
```

Audience guide: [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md)  

Gate every session on:

```bash
make verify
```

---

# Make targets

| Target | Purpose |
| --- | --- |
| `make install` | Install deps with uv (`prerelease=allow`) |
| `make env` | Create `.env` from `.env.example` |
| `make verify` | Full pre-flight diagnostics |
| `make validate` | Fast calm_v2 validation |
| `make train` | Package the agent model |
| `make inspect` | Voice + text Inspector |
| `make run` | API server on port 5005 |
| `make show-demo-data` | See demo data |
| `make reset-db` | Reseed SQLite from JSON |
| `make tutorial` | Print chapter / snippet map |
| `make clean` | Remove models, caches, demo db |
| `make clean-all` | Also remove `.venv` |

Run `make` alone for the grouped help screen.

---

# Troubleshooting

Always start with:

```bash
make verify
```

Common fixes are printed inline by the verifier (`make install`, `make env`,
`make reset-db`, `make clean && make train`).

---

# Rasa version

Pinned in `pyproject.toml`:

```text
rasa-pro==3.19.0.dev5
```

LLM: `gpt-5.2` in `integrations.yml` and `endpoints.yml` — do not set `temperature`.
Install with:

```bash
make install
```

This project uses **Rasa Maestro / Skills (`calm_v2`)** — not CALM v1 flows.

---

# Design principles

* Keep skills small; compose with `@skill.<name>`
* Put side effects in tools, not prose
* Confirm irreversible actions before calling mutating tools
* Write voice instructions as short spoken sentences
* Never commit secrets — use `.env` / `.env.example` only

---

# Disclaimer

This is a demo assistant for teaching and local exploration. It is not a
production telecom care system and does not connect to live network equipment.
