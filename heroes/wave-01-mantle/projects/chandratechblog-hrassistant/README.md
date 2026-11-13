# HR Bot

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/heroes-wave-01-mantle-projects-chandratechblog-hrassistant/devcontainer.json)

This cohort snapshot installs its own locked Rasa version; it does not track catalog upgrades.

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `uv run rasa train && uv run rasa inspect`. The terminal opens in this folder, and the creation log ends with `READY`. Training may make provider calls to index this resource's reference documents; see the setup requirements below.
- **You should see:** training finishes, then the Inspector starts. In a second terminal, `bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/print-inspector-url.sh"` prints its address.
<!-- codespaces:end -->

```text
Author:        Chandra Sekhar
Wave:          wave-01-mantle
Assessed on:   2026-09-19
Assessed by:   Chandra Sekhar
Verified with: rasa-pro 3.20.0.dev6, Python 3.11–3.12, uv
Audience:      HR teams and Rasa practitioners prototyping conversational HR support
Time:          15–20 minutes
Industry:      General
You learn:     How an HR assistant explains policies and creates leave requests and tickets after confirmation.
Catalog name:  HR policy, leave and ticket assistant
```

An HR support assistant built on the Rasa Mantle engine. It helps employees
understand general HR policies, check demo attendance and leave records, and
create or track HR support tickets through a conversational interface.

This project is part of **Wave 01 - Mantle** and targets `rasa-pro
3.20.0.dev6`. It uses Mantle skills and Python tools rather than the CALM-era
`domain.yml`, `config.yml`, intents, stories, and rules format.

## Capabilities

- Welcome employees and route them to the appropriate HR workflow.
- Explain general guidance for attendance, leave, remote work, conduct,
  benefits, payroll, and workplace accommodations.
- Look up an attendance record for an employee and date.
- Check a leave balance or submit a leave request after explicit confirmation.
- Create an HR support ticket after explicit confirmation.
- Track an existing ticket by ticket number.
- Support REST and Inspector channels.
- Support voice through Deepgram ASR and TTS when the required credentials are
  configured.

The assistant is designed to avoid inventing records, approvals, balances,
status updates, or employment decisions. General policy guidance is not legal
advice or an employee-specific decision.

## Project Structure

```text
agent.yml                 Agent persona, voice settings, and global rules
integrations.yml          LLM, embedding, and channel configuration
references/               General HR guidance and source/demo-data notes
  README.md               Text provenance and fictional-data status
  hr_policies.md          General HR guidance and privacy boundaries
skills/
  hr_concierge/           Welcome and route employees
  hr_policies/            Explain general HR policies
  hr_attendance/          Attendance lookup and demo data
  hr_leave_management/    Leave balance and request workflows
  hr_ticketing/           Ticket creation, tracking, and demo data
models/                   Generated model artifacts
```

Each skill contains a `skill.md`. Skills that access records also contain a
Python `tools.py` module and JSON-backed demo data.

## Requirements

- Python with the project virtual environment available on `PATH`.
- Rasa Pro `3.20.0.dev6`.
- An OpenAI API key for the configured orchestrator and embeddings.
- A Rasa license key.
- A Deepgram API key for voice features.

The required environment variables are:

```text
RASA_LICENSE
OPENAI_API_KEY
DEEPGRAM_API_KEY
```

Keep credentials in a local `.env` file or another secret store. Do not commit
secret values. The checked-in project configuration references environment
variables rather than embedding credentials in YAML.

## Run Locally

From this project directory, configure the environment variables and install
the locked dependencies:

```bash
uv sync
uv run rasa train
uv run rasa inspect
```

`uv sync` creates or updates the project environment from `uv.lock`. `uv run
rasa train` validates the agent and builds the model in `models/`. Run it again
after changing `agent.yml`, `integrations.yml`, or any skill. `uv run rasa
inspect` opens the Inspector interface for interactive testing.

The REST channel is enabled in `integrations.yml`. The Inspector is also
enabled for local conversations.

## Demo Records

The record tools use local JSON files and are intended for demonstrations, not
production HR data. Example identifiers include:

- Attendance: `E1001` on `2026-09-10` or `2026-09-11`.
- Leave balances: `E001`, `E002`, `E003`, or `E004` with leave type `annual` or
  `sick`.
- Existing tickets: `HR-10042` and `HR-10043`.

Demo ticket creation returns `HR-NEW-DEMO`, and demo leave submission returns
`LV-NEW-DEMO`. These operations do not connect to a live HR system or persist
new records.

## Privacy and Safety

- Request only the minimum information needed for the selected workflow.
- Never request passwords, full government identifiers, medical details, or
  unrelated personal information.
- Confirm ticket and leave-request details before submitting them.
- A received ticket or submitted leave request is not a resolution or approval.
- Use an approved HR channel for human support and urgent workplace concerns.

## Mantle Notes

Mantle documentation is bundled under `.rasa/docs/mantle/`. Consult it before
changing Mantle configuration, skill frontmatter, conditions, memory, or tool
integration syntax. This project intentionally does not contain CALM v1 files.