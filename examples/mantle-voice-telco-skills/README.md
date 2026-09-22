# Telano — Voice Telecom Care with Rasa Mantle

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv  # rasa-version-ignore: historical assessment; current checks in COMPATIBILITY.json
Installation:  rasa-pro 3.20.0 (automated check scope in COMPATIBILITY.json)
Audience:      Practitioners building voice telecom care agents with Rasa Skills
Time:          75–90 minutes
```

A production-style **voice telecom care agent** built with the new Rasa **Skills / Mantle** architecture and **Deepgram** for speech-to-text and text-to-speech.

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
| `sim_swap` | Move a mobile number to a new SIM, verified off the line being moved ([details](#sim-swap-the-number-cannot-vouch-for-itself)) |
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
                         │    Rasa Mantle     │
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
│   ├── sim_swap/
│   ├── human_handoff/
│   └── goodbye/
│
├── tools/
│   └── telco.py
│
├── lib/
│   ├── database.py
│   └── sim_swap.py
│
├── data/
│   └── source/
│
├── scripts/
│   ├── verify_setup.py
│   └── show_demo_data.py
│
├── tests/
│   └── test_sim_swap.py
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
Mantle `@tool` under `tools/`.

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

# SIM swap: the number cannot vouch for itself

A SIM swap moves a phone number onto a new SIM card. It is also the standard
way to take over someone's number. The caller says they lost their phone and
asks to move "their" number to a SIM they are holding. If the swap goes
through, every text and call for that number, one-time codes included, now
reaches them.

The `sim_swap` skill is built around one rule: **the line being replaced
cannot be the only witness to its own replacement.**

- **A code sent by SMS or voice call to that line proves nothing.** The check
  is circular. And if the attacker already controls the line through call
  forwarding, a hijacked voicemail or an earlier port, the code goes to the
  attacker and approves the swap for them.
- **A PIN, a date of birth or a security answer never approves a swap on its
  own.** Those can be phished, bought or guessed, however correct they are.
- Independence is a property of the channel *relative to the action's
  target*. An SMS code is a reasonable factor for many requests. For moving
  the number it was sent to, it is worthless.

Only two channels count: a code pushed to the Telecom of Rasa app on a device
that was **registered before the call**, and a **store visit with photo ID**.
A device enrolled during the call was enrolled on the word of the same
unverified caller, so it does not count.

### Where the rule is enforced

`lib/sim_swap.py` holds the policy. It is pure Python with no I/O.
`evaluate_swap(target_line, verification)` returns a decision with one of five
reason codes:

| Reason | Meaning |
| --- | --- |
| `no_verification` | Nothing usable: none at all, or a record that is malformed, has an unknown channel, did not pass, or came from a push to a device enrolled during the call |
| `knowledge_only` | The factor was a PIN, date of birth or security answer |
| `target_changed` | The verification was issued for a different line than the one now requested |
| `circular_verification` | An SMS or call code went to the target line itself |
| `allowed` | An app push to a device registered before the call, or a store ID check, was issued for this line and passed |

The policy fails closed. `passed: "true"` as a string, a missing field or an
unknown channel all come back as `no_verification`. It never raises.

`skills/sim_swap/tools.py` runs that policy on the first line of
`request_sim_swap`, before the ICCID is read and before anything is written. A
refusal returns `ok: false` with a reason code and no swap reference. The
skill prose also tells the model never to offer an SMS to the line and never to
ask knowledge questions. The prose shapes what the model tries, and the
guard decides what actually happens. Other rules the code enforces:

- "Registered before the call" is a timestamp comparison. The call start is
  fixed on the first SIM swap tool call, taken from the earliest tracker
  event, and kept in memory. A device counts only if its `registered_at` is
  earlier than that.
- Before verification the caller is told only that a code went to "a device
  already registered to the account". The device's name, id and type stay out
  of tool results and memory.
- When the caller switches to a different line, the earlier verification is
  discarded, and switching back does not bring it back.
- The push code is compared and then dropped. It is never written to memory
  or returned in a tool result, and log lines show only its length.
- The send tool issues only `app_push` or `store_id_check`, each handled by
  its own branch. Adding a name to `INDEPENDENT_CHANNELS` does not create a
  new way to approve a swap.
- Two wrong codes lock the call, and re-sending a push does not reset the
  count. The skill then hands off to the identity team
  through `human_handoff`.
- A successful request returns `status: queued` and `active: false`.
  `check_swap_status` reports the status stored for the reference and never
  treats a queued request as an active SIM. The agent says only what the
  receipt proves.

### Escalation boundary

When no independent path exists, the agent does **not** activate anything
remotely. That covers a customer with no registered device (customer `124`
in the fixtures), a caller who cannot use the app or visit a store, and a call
that is locked out. The agent says the swap cannot be approved over the phone
and hands off to the identity team. A store ID check is never completed from
the call: store staff finish it in person.

This is a teaching policy for a fictional carrier, and the whole flow runs on
synthetic data. It is not any real carrier's SIM swap procedure. It sends no
messages, contacts no provisioning system, and makes no claim about what a
real carrier's fraud controls require.

### Run the tests

```bash
make install
make test
```

`tests/test_sim_swap.py` needs no model, no network and no credentials. It
calls the policy and the tools directly with a fake context and a throwaway
SQLite file:

```text
test_sms_code_to_the_line_being_replaced_is_refused
test_knowledge_factors_never_authorise_a_swap
test_app_push_to_a_registered_device_authorises_the_swap
test_changing_the_target_line_discards_the_verification
test_refusal_returns_no_swap_reference
test_a_queued_request_is_not_reported_as_active
test_malformed_verification_fails_closed
test_unverified_caller_learns_nothing_about_the_device
test_device_registered_during_the_call_does_not_count
test_widening_the_channel_set_does_not_open_a_new_path
test_resending_a_push_does_not_reset_the_attempt_budget
```

The test module's docstring records seven deletion checks. With the guard
removed from `request_sim_swap`, eight of the eleven tests fail. The
docstring also records which checks stop a swap (the guard, the target
binding, the call-start comparison, the explicit channel gate, the attempt
budget) and which only change the reason code (the knowledge
and circular checks, since the channel allowlist refuses those records
anyway).

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
| `make install` | Install deps with uv |
| `make env` | Create `.env` from `.env.example` |
| `make verify` | Full pre-flight diagnostics |
| `make validate` | Fast Mantle validation |
| `make test` | SIM swap policy and tool tests (no model, no keys) |
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
rasa-pro==3.20.0
```

LLM: `gpt-5.2` in `integrations.yml` and `endpoints.yml` — do not set `temperature`.
Install with:

```bash
make install
```

This project uses **Rasa Mantle / Skills (`rasa.mantle`)** — not CALM v1 flows.

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
