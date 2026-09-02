# Atlas on Google Gemini — voice travel agent with local embeddings

```text
Author:        Samrudha Kelkar
Kind:          example
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners who want a Mantle voice agent without an OpenAI key
Time:          30–45 minutes
```

The [Atlas voice travel agent](../../examples/mantle-voice-agent) reconfigured
to run on **Google Gemini** for routing and conversation, and on **local
sentence-transformers embeddings** for the knowledge base — so the whole agent
runs without an OpenAI account of any kind.

It is maintained on the catalog pin like everything else here, so it does not
go stale behind the rest of the repository. What that costs is one honest
caveat about CI coverage — see
[Provenance and verification](#provenance-and-verification).

---

## What is different here

Three changes from the upstream Atlas, and they are the whole contribution:

| | Upstream Atlas | This resource |
|---|---|---|
| LLM | `openai` / `gpt-4.1-mini` | `gemini` / `gemini-2.5-flash` |
| Reference embeddings | `openai` / `text-embedding-3-large` | `huggingface_local` / `sentence-transformers/all-MiniLM-L6-v2` |
| Keys needed | `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY` | `RASA_LICENSE`, `GEMINI_API_KEY`, `DEEPGRAM_API_KEY` |

The provider swap alone is not enough to drop OpenAI: the reference index
reaches for OpenAI embeddings independently of the conversation LLM, so an
agent configured for Gemini would still have failed to train without an OpenAI
key. Moving embeddings local is what closes that gap, and it is the part worth
copying.

Everything is configured live — there are no commented-out fragments to
reassemble. The OpenAI equivalents are kept as comments in `integrations.yml`
and `endpoints.yml` if you want to swap back.

### What it costs

`sentence-transformers` pulls in **torch**, and the first `make train`
downloads the embedding model (~90 MB). That is a real cost, and it is why this
configuration lives here rather than becoming the catalog default: readers
following the main tutorial should not pay a multi-hundred-megabyte install for
a provider they are not using.

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
| `GEMINI_API_KEY` | LLM for routing + conversation (`gemini-2.5-flash`) |
| `DEEPGRAM_API_KEY` | Speech-to-text **and** text-to-speech |

**No `OPENAI_API_KEY`.** That is the point of this resource — see
[What is different here](#what-is-different-here).

`make verify` reads `llm.api_key_env` out of `integrations.yml` and checks the
key that configuration actually names, so if you swap providers it follows you
rather than checking whichever key happens to be exported.

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
                         │    Rasa Mantle     │
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
| `integrations.yml` | OpenAI LLM + Inspector Deepgram ASR/TTS |
| `memory.yml` | Project-wide session memory |
| `responses.yml` | Project-wide verbatim responses |
| `skills/` | One folder per skill |
| `tools/travel.py` | Shared `@tool` functions |
| `lib/database.py` | SQLite demo backend |
| `data/source/` | JSON seed data for Maya’s trips |
| `scripts/verify_setup.py` | Pre-flight diagnostics |

This is a **Skills / Mantle** project. Do **not** add CALM v1 files
(`config.yml`, `domain.yml`, flow YAMLs under `data/`).

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

---

## Why this is a separate resource

It was originally offered as a change to
[`tutorials/rasa-voice-agent-tutorial`](../../tutorials/rasa-voice-agent-tutorial)
([#1](https://github.com/RasaHQ/rasa-community-resources/pull/1)). As a change
to the tutorial it would have made `sentence-transformers` — and therefore
torch — a required dependency for every learner, and removed the
`openai-embeddings` model group that the tutorial's default path uses. Landing
it here keeps the tutorial's install small while keeping the configuration
complete, runnable, and credited.

## Provenance and verification

Honest about who checked what, because the two are not the same:

| Claim | Verified by | When | Against |
|---|---|---|---|
| Runs end to end on Gemini — `make verify`, `make train`, and a live Deepgram voice conversation via `make inspect` | Samrudha Kelkar | 2026-08-16 | `3.19.0.dev5`, on the original submission |
| Installs from the committed `uv.lock` and passes `validate_project` | Rod Rivera | 2026-08-26 | the current catalog pin |

**The live Gemini path has not been re-verified on the current pin.** No
`GEMINI_API_KEY` was available at review time, so `rasa train` is skipped here
and in CI — the resource declares the key in `[tool.rasa-catalog]
required-secrets`, which turns that into a visible skip rather than a failure
that looks like a broken project. Add `GEMINI_API_KEY` to the repository
secrets and this resource starts training in CI like any other.

Until then: it installs and validates on the current pin, and the end-to-end
Gemini run is Samrudha's claim against the version in the table above. If you
run it and something has drifted, please open an issue.

Changed during review, from the original submission:

- Gemini and the local embedding group are the **live** configuration rather
  than commented alternatives, since this resource exists to show that path.
- `scripts/verify_setup.py` picked its provider with
  `if llm_var == "GEMINI_API_KEY" or os.getenv("GEMINI_API_KEY")`. A developer
  with a stale `GEMINI_API_KEY` exported but OpenAI configured would have had
  their `OPENAI_API_KEY` silently skipped. It now reads the configured provider
  and only that; the duplicated YAML-sniffing block in `check_secrets` and
  `check_connectivity` was collapsed into one helper.
- `name:` and `description:` moved out of the `agent:` block in `agent.yml`,
  where the engine discards them. Samrudha found this class of bug and had
  already fixed `rules:` and `references:` in the original submission; the
  catalog-wide fix that followed is credited to him.
- The `tutorial/` chapter-paste tree was dropped. It belongs to the tutorial,
  not to a provider configuration.
- Brought from `3.19.0.dev5` onto the current catalog pin, with the lock
  regenerated.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
