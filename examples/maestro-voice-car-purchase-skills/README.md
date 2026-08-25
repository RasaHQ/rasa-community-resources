# Autono — Voice Car Purchasing with Rasa Maestro

```text
Author:        Rod Rivera
Assessed on:   2026-08-25
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev7, Python 3.11+, uv
Audience:      Practitioners building voice auto-retail agents with Rasa Skills
Time:          75–90 minutes
```

A production-style **voice car-purchase agent** built with the new Rasa **Skills / Maestro** architecture and **Deepgram** for speech-to-text and text-to-speech.

Autono is the voice assistant for **Rasa Motors**. It can research the inventory, recommend cars, reserve a vehicle at a dealer, book a dealer appointment, run a credit check, work out affordability, quote financing, and hand the conversation off to a human — all through voice or text.

This repository is designed to be useful in two ways:

1. **Run the finished agent immediately**
2. **Build it yourself step by step** using the live-session tutorial in [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md)

> **Demo customer:** Alex Rivera
> A seeded SQLite dealership environment is included under `data/source/`, so you can explore the complete agent without connecting to a real DMS or lender.

> Suggested public repository name: **`rasa-maestro-voice-car-purchase-skills`**

---

## What Autono can do

| Skill                         | Capability                                                          |
| ----------------------------- | ------------------------------------------------------------------- |
| `intro`                       | Introduce Autono and orient the customer                            |
| `car_faq`                     | Answer common questions about reservations, financing, and visits   |
| `check_balance`               | Look up balances across the customer's accounts                     |
| `research_cars`               | Search inventory and recommend cars for a budget and body type      |
| `shop_cars`                   | Check availability, suggest alternatives, and list dealers          |
| `reserve_car`                 | Hold a specific car at a specific dealer, with confirmation         |
| `schedule_dealer_appointment` | Book a dealer visit, reserving the car first when needed            |
| `check_credit_score`          | Validate identity, then pull a credit score                         |
| `check_affordability`         | Estimate an affordable monthly payment from income and debts        |
| `check_existing_loans`        | List current loans and their repayments                             |
| `calculate_loan`              | Quote monthly payments across 36, 48, and 60 month terms            |
| `human_handoff`               | Create a ticket for a live sales specialist                         |
| `goodbye`                     | Close the conversation gracefully                                   |

`schedule_dealer_appointment` demonstrates **skill composition**: if no car has been reserved yet, Autono invokes the `reserve_car` capability first, then continues booking the visit.

---

## Why this project exists

Autono is a compact example of how to build agents that combine **LLM flexibility with deterministic controls**.

Instead of placing an entire car-buying assistant inside one large prompt, the agent is decomposed into focused **skills** with explicit control over:

* which tools are available
* when tools become available
* when user confirmation is mandatory
* which instructions enter the model context
* which steps must happen in a strict order
* which responses must use exact wording

That makes this repository useful both as an automotive demo and as a reference for building more reliable agentic applications with Rasa.

---

## Architecture

```text
                         ┌─────────────────────┐
                         │      Customer       │
                         │    voice or text    │
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
             │   Skills   │  │   Tools    │  │  Car FAQ    │
             │            │  │            │  │ references  │
             │ reserve    │  │ @tool funcs│  │             │
             │ research   │  └──────┬─────┘  └─────────────┘
             │ financing  │         │
             │ scheduling │         ▼
             └────────────┘  ┌──────────────┐
                             │ SQLite demo  │
                             │  dealership  │
                             └──────────────┘
```

---

# Quick start

## 1. Prerequisites

You need:

* **Python 3.11 or 3.12**
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

When possible, it tells you **exactly what is wrong and how to fix it**.

---

## 4. Train

```bash
make train
```

This validates the project and packages the agent.

---

## 5. Talk to Autono

```bash
make inspect
```

Rasa Inspector will open in your browser.

Use the **microphone** to speak with Autono through Deepgram, or type messages when you want a text fallback.

Try:

> I'm looking for a compact SUV under thirty thousand.

> Do you have a Toyota RAV4 in stock?

> Reserve the RAV4 at Auto City Motors.

> Book me a test drive next week.

> What would the monthly payment be over sixty months?

> Can you check my credit score?

> I need to speak to a human.

---

# Demo environment

Autono ships with a small local dealership environment backed by SQLite.

The seeded customer is:

```text
Alex Rivera
```

Inspect the demo accounts, loans, and a sample of the inventory with:

```bash
make show-demo-data
```

If you modify the data while testing and want to return to the original state:

```bash
make reset-db
```

That deletes `data/autono.db`, which is rebuilt from the fixtures on the next tool call.

The source fixtures live under:

```text
data/source/
```

| Fixture                | Contents                                                  |
| ---------------------- | --------------------------------------------------------- |
| `users.json`           | Demo customers, including Alex Rivera                     |
| `accounts.json`        | Checking and savings balances                             |
| `loans.json`           | Existing loan commitments                                 |
| `cars.json`            | Rasa Motors inventory across five dealers                 |
| `search_results.json`  | Canned review articles used for recommendations           |
| `reservations.json`    | Empty — filled in as the agent reserves cars              |
| `appointments.json`    | Empty — filled in as the agent books dealer visits        |
| `handoff_tickets.json` | Empty — filled in when a customer asks for a human        |

No external dealership, credit bureau, or lender API is required.

---

# Project structure

```text
.
├── agent.yml
├── integrations.yml
├── memory.yml
├── responses.yml
│
├── skills/
│   ├── intro/
│   ├── goodbye/
│   ├── car_faq/
│   ├── check_balance/
│   ├── research_cars/
│   ├── shop_cars/
│   ├── reserve_car/
│   ├── schedule_dealer_appointment/
│   ├── check_credit_score/
│   ├── check_affordability/
│   ├── check_existing_loans/
│   ├── calculate_loan/
│   └── human_handoff/
│
├── tools/
│   └── automotive.py
│
├── lib/
│   ├── database.py
│   ├── cars.py
│   └── financing.py
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
    └── snippets/
```

### `agent.yml`

Defines the Autono persona and agent-level configuration, including voice-related behaviour and the rule that no car, price, or dealer may be invented.

### `integrations.yml`

Configures external integrations including:

* OpenAI
* Rasa Inspector
* Deepgram speech-to-text
* Deepgram text-to-speech

Maestro projects use `integrations.yml`; there is no classic `credentials.yml` in this project.

### `memory.yml`

Defines project-wide memory available across skills, including the reserved `car_model`, `car_price`, and `dealer_name` that later skills reuse.

### `responses.yml`

Contains deterministic response templates, including wording that should not be freely generated by the model.

### `skills/`

One directory per Maestro skill. Each skill encapsulates the instructions and controls for a specific capability.

### `tools/`

Shared Python functions exposed to the agent with Rasa's `@tool` interface, all in `tools/automotive.py`.

### `lib/`

Helpers for the local demo backend: `database.py` (SQLite dealership), `cars.py` (inventory and research search), and `financing.py` (mock lender).

### `data/source/`

Seed data used to initialise the demo dealership.

### `tutorial/`

A complete live-session walkthrough plus paste-ready snippets for teaching or rebuilding the agent from scratch.

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

# Example: safe car reservation

Reserving a car is a useful example because different parts of the journey need different levels of control.

Autono may converse naturally while understanding:

> "Hold that little Kia for me, the used one."

But the system can still enforce requirements such as:

1. confirm the exact model against live inventory
2. identify the dealer holding that car
3. capture the advertised price
4. establish why the car is being held — test drive, purchase intent, or a simple hold
5. read the details back to the customer
6. receive explicit customer approval
7. only then write the reservation

`reserve_car` implements this with a `:::ordered_block` for vehicle selection, a `tool_constraints` gate on `finalize_reservation`, and a mandatory confirmation utterance.

The language can remain flexible while the **business invariant stays deterministic**.

---

# Skill composition

Skills do not need to become monolithic just because a user journey spans multiple capabilities.

For example:

```text
schedule_dealer_appointment
      │
      ├── car already reserved ─────────► book appointment
      │
      └── no car reserved
              │
              ▼
          reserve_car
              │
              ▼
        book appointment
```

`reserve_car` writes `car_model`, `car_price`, and `dealer_name` into project memory, so the scheduling skill — and later the financing skill — can pick up where it left off.

This lets capabilities remain independently understandable and reusable while Maestro coordinates them into a larger customer journey.

---

# Voice stack

Autono uses **Deepgram** for both sides of the voice interaction:

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

Skill instructions are written for speech: short sentences, one question at a time, and at most two or three options read aloud before asking the customer to choose.

If you do not want to use voice while developing, Inspector also supports typed conversations.

---

# Live tutorial

Want to build Autono rather than just run it?

Start here:

```text
tutorial/TUTORIAL.md
```

The tutorial is designed for a live coding session and includes:

* the build sequence
* explanation of each Maestro concept
* commands to run
* test conversations
* paste-ready code
* checkpoints
* troubleshooting notes

Snippets are available under:

```text
tutorial/snippets/
```

You can therefore use this repository either **top-down**:

```text
clone → run finished agent → inspect implementation
```

or **bottom-up**:

```text
follow tutorial → paste snippets → build Autono progressively
```

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
| `make show-demo-data` | Display Alex's accounts, loans, and sample inventory    |
| `make reset-db`       | Reset the SQLite dealership from seed data              |
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

Then run:

```bash
make verify
```

The verifier also checks the license expiry date.

### OpenAI errors

Confirm that:

```bash
OPENAI_API_KEY=...
```

is present and valid.

`make verify` performs a live connectivity check.

### Deepgram voice is not working

Confirm that:

```bash
DEEPGRAM_API_KEY=...
```

is configured.

The same key is used by Inspector for speech recognition and speech synthesis.

You can continue testing Autono through text while diagnosing voice configuration.

### Demo data looks wrong

Reset it:

```bash
make reset-db
```

Then inspect it:

```bash
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
rasa-pro==3.19.0.dev7
```

This is a **pre-release** version — the Maestro / Skills engine (`rasa.calm_v2`)
ships only on the `3.19.0.devN` line — so installation uses:

```bash
uv sync --prerelease=allow
```

A few implementation details are specific to the Maestro architecture used by this release:

* tools import from `rasa.calm_v2.tools`
* tools use Rasa's `@tool` interface rather than classic `rasa_sdk` Action classes
* channels are configured in `integrations.yml`
* Inspector can configure Deepgram ASR and TTS directly

If you are comparing this repository with older Rasa projects, expect the structure to look different. In particular there is no `config.yml`, no `domain.yml`, and no flow YAML under `data/`.

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

If you change the demo dealership and need a clean test environment:

```bash
make reset-db
```

---

# Design principles

Autono intentionally follows a few principles that transfer well beyond car sales.

### Keep skills small

A skill should represent a coherent capability, not the entire assistant.

### Keep business logic in tools

Skills describe behaviour and orchestration. Python tools perform application operations such as searching inventory, writing reservations, and quoting finance.

### Make side effects explicit

Reserving a car, booking a dealer visit, or opening a handoff ticket deserves stronger controls than an informational query about stock.

### Never let the model invent inventory

Every model, price, dealer, and availability answer comes from a tool result. This is enforced in the persona, in the agent rules, and in the skill instructions.

### Prefer deterministic guarantees over prompt wishes

If something **must** happen, encode that requirement structurally instead of merely asking the model to remember it.

### Make the repository runnable

Examples are much more useful when developers can execute them, inspect the state, break them, reset them, and try again.

---

# Important

Autono is a **demonstration application**.

The included SQLite dealership, customer records, reservations, appointments, credit scores, and financing quotes are simulated and are not suitable for handling real customer data, credit decisions, or vehicle sales.

A production implementation would require additional controls around authentication, authorisation, auditability, privacy, regulatory compliance around consumer credit, fraud prevention, observability, resilience, and integration with authorised dealer management and lending infrastructure.

---

# License

Use this project with a valid Rasa Pro Developer Edition license.

Review the [Rasa Developer Terms](https://rasa.com/developer-terms).
