# NourishHer — Voice Nutrition Companion

    Author:        Malar Saravanan (@Malar-saravanan)
    Wave:          wave-01-mantle
    Assessed on:   2026-09-18
    Assessed by:   Malar Saravanan (@Malar-saravanan)
    Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
    Audience:      Practitioners building voice-first, tool-using health/coaching agents on the Mantle engine
    Time:          60–90 minutes to install, train, and inspect

> **Frozen wave-01-mantle snapshot.** Pinned to `rasa-pro 3.20.0.dev6` and not
> migrated forward — see [`docs/SNAPSHOTS.md`](../../../../docs/SNAPSHOTS.md).
> `Verified with:` records the version the author ran; `uv.lock` resolves to it.

A voice-first women's health nutrition companion, built with Rasa Skills
(Mantle). It builds and maintains a personal nutrition profile, plans meals,
logs food naturally, recalls history, and coaches on everyday habits through
natural conversation — with **optional** condition-aware support
(hypothyroidism, PCOS, type 2 diabetes, fertility/preconception). Health
context is never required. Evolved in place from the earlier condition-only
"Sage" build.

** production-grade.** Nutrient numbers come from the live USDA
FoodData Central API; profile, meal logs, and saved plans persist in a real
file-backed per-user store (`lib/store.py`, under `data/`). Nothing is
seeded or fabricated. A deterministic test suite (`make test`) covers the
persistence and tool layer with no LLM/network calls.

Built during the Rasa Heroes wave-01-mantle cohort. Runs `rasa-pro==3.20.0.dev6`
— the latest release on PyPI as of the 2026-09-01 migration from this project's
original `3.19.0.dev5` (pre-Mantle) pin.

> ⚠️ **Mantle is experimental.** `rasa train` prints this verbatim: *"Mantle
> is currently experimental and under active development... Don't use it to
> process sensitive data."* NourishHer handles self-reported health/medication
> data — keep that in mind for anything beyond local testing.

**Not a diagnostic or treatment tool.** NourishHer coaches on diet for a condition
the person already reports having (or is being evaluated for). It never
diagnoses, never adjusts medication, and never gives dosage advice. Red-flag
symptoms (possible hypoglycemia, thyroid crisis, concerning menstrual-pattern
change, disordered-eating signals) trigger a hard, verbatim hand-off to a
human/clinician — never an LLM-generated answer.

## Prerequisites

- macOS/Linux, Python 3.11–3.13, [`uv`](https://astral.sh/uv) installed
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- A free Rasa Pro Developer Edition license — [request one here](https://rasa.com/rasa-pro-developer-edition-license-key-request/).
- API keys for OpenAI (LLM, primary), Groq (LLM, fallback only — see
  [integrations.yml](integrations.yml)), Gemini (embeddings), Deepgram
  (voice), and optionally USDA FoodData Central. If you already have a
  working `.env` for another Mantle voice agent in this catalog (e.g.
  `examples/mantle-voice-agent`), you can copy `RASA_LICENSE` /
  `GEMINI_API_KEY` / `DEEPGRAM_API_KEY` straight from there — same providers,
  same setup — but you will still need your own `OPENAI_API_KEY` and
  `GROQ_API_KEY`.

## Quick start

```bash
make install   # install dependencies into .venv (uv)
make env       # create .env from .env.example
# fill in RASA_LICENSE, OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY,
# DEEPGRAM_API_KEY in .env
# (USDA_FDC_API_KEY defaults to a shared, rate-limited DEMO_KEY — get your own
# free key at https://fdc.nal.usda.gov/api-key-signup if you'll test more than
# a couple of food lookups)
make verify    # pre-flight diagnostics — should be all green before training
make test      # run the deterministic persistence/tool tests (no LLM/network)
make train     # build the agent model
make inspect   # talk to NourishHer in the Rasa Inspector — voice (mic) or text
```

### Embedded web UI (the "live app")

A self-contained chat UI lives in [`ui/index.html`](ui/index.html) — a warm,
voice-capable companion interface that talks to the assistant over Rasa's
REST channel. It uses the browser's built-in speech APIs (mic input + spoken
replies, toggle with 🔊 **Speak**), so it needs no extra keys, and it keeps a
**stable per-user id** in `localStorage` so your profile, meal log, and plans
persist across sessions (the backend keys its file store by that same id).

Run it in two terminals:

```bash
make api    # terminal 1 — API server with CORS enabled (http://localhost:5011)
make ui     # terminal 2 — serves the UI at http://localhost:8080
```

Then open **http://localhost:8080** in a browser (Chrome/Edge for voice
input; text works everywhere). Point the UI at a different API with
`?api=http://host:port`. Custom ports: `make api API_PORT=5015` and
`make ui UI_PORT=9000`.

The UI auto-retries on an empty reply and shows a clear status while it
waits — rare in normal operation now that OpenAI is the primary LLM, see the
note below for when it can still happen. For embedding in an existing app,
`ui/index.html` is a single static file: host it anywhere and set its
`?api=` to your running assistant.

### Testing without a browser/mic (REST)

`make inspect` opens a browser Inspector and needs a working microphone for
voice. To test from a terminal instead:

```bash
uv run rasa run --enable-api --port 5011 &
curl -s -X POST http://localhost:5011/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test1","message":"hi"}'
```

Send further messages with the same `"sender"` id to continue the same
conversation. This is exactly how the live build was tested end to end.

### What to try

[`docs/demo-queries.md`](docs/demo-queries.md) is a guided first session plus a
capability-by-capability list of example utterances — onboarding, meal logging,
live USDA nutrition lookups, meal planning, history, coaching, each of the four
conditions, the verbatim safety hand-offs, and professional referral. Start
there to exercise everything the assistant does.

### Evaluation

Two suites:

```bash
make test           # deterministic — persistence + tools, no LLM or network (9 cases)
make e2e            # live — drives the orchestrator LLM end to end (4 assertion-based cases)
make e2e-coverage   # make e2e plus a coverage report under e2e_coverage/
```

`make test` is offline and hermetic. `make e2e` needs a trained model and
working keys, and exercises live routing, tool-calling, and the verbatim
safety hand-off, so its result depends on which provider answers.
[`tests/e2e_test_cases.yml`](tests/e2e_test_cases.yml) holds the cases;
[`docs/mantle-features.md`](docs/mantle-features.md) records what automation
does and does not cover — condition-skill routing and the levothyroxine
reminder are checked conversationally, because the e2e fixture schema cannot
seed the `session.project.*` flags they gate on.

#### Sample evaluation report (latest run)

Recorded on **2026-09-19** on Windows 11, **Python 3.13.15** (`uv`), **rasa-pro
3.20.0.dev6**, trained model `models/20260919-221612-sour-serif.tar.gz`. Primary
LLM: OpenAI `gpt-4o` (Groq fallback configured but not exercised in this run).

| Suite | Command | Result | Notes |
|-------|---------|--------|-------|
| Unit / store | `make test` | **9/9 passed** | `unittest` over `tests/`; no network |
| E2E harness | `make e2e` | **4/4 passed** | ~52s; live LLM + tools |
| E2E + coverage | `make e2e-coverage` | **4/4 passed** | Reports under `e2e_coverage/` (gitignored) |

**E2E assertion accuracy (harness summary):**

| Assertion type | Accuracy |
|----------------|----------|
| `flow_started` | 100% |
| `bot_uttered` | 100% |

**Cases exercised:** `greets_on_session_start`, `log_a_meal_naturally`,
`nutrition_lookup_uses_real_data` (routing only; USDA reply not asserted),
`safety_escalation_on_hypoglycemia` (verbatim urgent hand-off wording).

**Not covered by this automation** (unchanged): condition-skill routing after
full intake, levothyroxine reminder gate — see manual steps in
[`tests/e2e_test_cases.yml`](tests/e2e_test_cases.yml) and
[`docs/demo-queries.md`](docs/demo-queries.md).

**Ad-hoc REST smoke** (optional, not part of `make e2e`): with
`uv run rasa run --enable-api --port 5011`, sender `sample-queries-run` received
coherent replies for intro, partial intake, meal log, and a live USDA lookup
(e.g. chana dal protein/iron per 100 g); files appeared under
`data/profiles/` and `data/meal_logs/`. Helper:
[`scripts/run_sample_queries.py`](scripts/run_sample_queries.py).

On Windows without `make`, use the equivalent `uv run` commands from Quick start
and replace `make test` / `make e2e` with:

```bash
uv run python -m unittest discover -s tests -v
uv run rasa test e2e tests/e2e_test_cases.yml
uv run rasa test e2e tests/e2e_test_cases.yml --coverage-report --coverage-output-path e2e_coverage
```

### LLM provider: OpenAI primary, Groq fallback

The orchestrator runs on OpenAI (`gpt-4o`). Groq (`gpt-oss-120b`) is a pure
fallback, wired as a weighted LiteLLM router in
[`integrations.yml`](integrations.yml): OpenAI serves every turn while it is
healthy, a failed call retries on Groq within the same turn, and repeated
OpenAI failures cool it out of rotation for about a minute so a downed
provider is not retried on each turn. Groq is never load-balanced against
OpenAI.

Groq's free tier caps at 8000 tokens/minute per model. A turn (system prompt
plus tool schemas) runs 2,500–3,500 tokens, so Groq only risks a
rate-limited empty reply while carrying sustained fallback traffic during an
extended OpenAI outage — the Bug 8 scenario below.

## Known open issues

- **Bug 8 (reliability, engine-level):** when an LLM call fails partway
  through a multi-tool turn, the Mantle engine (`3.20.0.dev6`) can return an
  empty response *and* leave flow state in the just-completed flow, with
  nothing surfaced — later turns then answer generically without leaving it.
  Recovering flow state after a mid-turn failure is the engine's
  responsibility, not the skill's; the behaviour was reproduced independently
  by another Rasa user and is filed as upstream feedback. NourishHer only
  influences how *often* it triggers: `intake_profile`'s final turn is
  token-heavy (`activate` → `set_fields` → `save_health_profile` →
  `complete_skill`), which on Groq's free-tier TPM cap reliably hit it right
  after the profile saved. With OpenAI primary the trigger now needs a
  sustained OpenAI outage. Workaround: start a fresh session (new REST
  `sender` id, or restart the Inspector) if a conversation goes generic and
  repetitive.
- **Bug 7:** the `hypothyroidism_nutrition` levothyroxine timing reminder is
  meant to play verbatim and automatically, but **is not verified firing
  reliably live** — three fix attempts are recorded, and the rate-limit
  stalls of Bug 8 repeatedly blocked reaching a clean state to test it. If
  you run the hypothyroidism flow and don't see the reminder, that is this
  known gap, not a new bug; the dietary guidance itself is still correct.

## Architecture

```text
              Person (voice or text)
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   Rasa Inspector             REST webhook
   Deepgram ASR/TTS           (web UI / curl)
          └────────────┬────────────┘
                       ▼
              ┌───────────────────┐
              │    Rasa Mantle    │
              │ skill routing     │
              │ memory + control  │
              │ LLM: OpenAI→Groq  │
              └─────────┬─────────┘
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Skills         Tools       References
       (16)           (15)        RAG (Gemini)
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
     USDA FoodData         per-user file store
     Central (live)        data/ profiles,
                           meal_logs, plans
```

- [`docs/capabilities.md`](docs/capabilities.md) — one-page overview: skills,
  tools, memory/persistence, and which paths are LLM-driven vs deterministic.
- [`docs/diagrams/nourishher-architecture.drawio`](docs/diagrams/nourishher-architecture.drawio)
  and [`nourishher-capabilities.drawio`](docs/diagrams/nourishher-capabilities.drawio)
  — editable draw.io source for the diagrams above.

Open the `.drawio` files at [app.diagrams.net](https://app.diagrams.net) or in
the draw.io VS Code extension. See also [`AGENTS.md`](AGENTS.md) for the layout
and flow overview.

## What makes this a genuine multi-condition build

- **Comorbidity from day one**: `intake_profile` collects all four
  condition areas in one pass (not just the first one mentioned), since a
  real person may be managing more than one at once (PCOS + hypothyroidism
  is a common pairing).
- **Real external data, presented clearly**: nutrient lookups come from the
  USDA FoodData Central API (`lib/usda_client.py`), not a fabricated demo
  dataset. Every food answer is a macro table and a micro table (amount +
  %daily-value per row, "per 100 g" basis always stated) — %DV is computed
  in code from the FDA's published adult Daily Values, not guessed by the
  LLM. Condition skills also give general, non-prescriptive lifestyle and
  activity guidance (never a specific exercise program).
- **Cross-session memory, the right store for each kind**: condition flags,
  meds, and allergies persist in project `memory.yml`; the freely-editable
  profile, the append-only meal/symptom log, and saved plans persist in a
  per-sender file store (`data/profiles/`, `data/meal_logs/`,
  `data/meal_plans/`). Project memory went write-once-per-field in
  `3.20.0.dev4+`, so a log that grows across many turns cannot live there.
- **A genuine food/medication interaction**: `hypothyroidism_nutrition`
  repeats a verbatim reminder that levothyroxine must be taken on an empty
  stomach, separated from calcium/iron supplements and high-fiber/soy foods
  — a real timing interaction, not medical advice about the drug itself.
- **Deterministic safety escalation**: `safety_escalation` never uses
  `metadata.rephrase: true` — wording for red-flag hand-offs is fixed.

See [`AGENTS.md`](AGENTS.md) for the full project layout and ground rules.
