# Rasa Maestro project — Autono voice car purchasing

This directory is a **Rasa Maestro** agent (Skills / calm_v2) that teaches
building a **voice** car-purchase assistant for Rasa Motors with **Deepgram**
ASR + TTS.

## Layout

- `agent.yml` — identity, persona (Autono), voice flags, rules
- `integrations.yml` — OpenAI LLM + Inspector channel with Deepgram ASR/TTS
- `endpoints.yml` — platform services read by `rasa train` / `rasa inspect`
  (contextual response rephraser, model groups)
- `memory.yml` — project-wide memory (`session.project.*`), including the
  reserved `car_model`, `car_price`, and `dealer_name`
- `responses.yml` — project-wide verbatim responses (greeting override)
- `skills/<name>/` — one skill per folder (`skill.md`, optional `memory.yml`,
  `responses.yml`, `references/`)
- `tools/automotive.py` — shared `@tool` functions (imported via `import_tools`)
- `lib/` — shared Python helpers: `database.py` (SQLite dealership),
  `cars.py` (inventory + research search), `financing.py` (mock lender)
- `data/source/` — JSON seed data; `cars.json` and `search_results.json` are
  read directly by `lib/cars.py` and are not database tables
- `scripts/` — `verify_setup.py` (pre-flight) and `show_demo_data.py`
- `tutorial/` — live-session script and paste-ready snippets

## Build loop

```bash
make install   # uv sync --prerelease=allow
make env       # copy .env.example -> .env, then fill in the keys
make verify    # pre-flight diagnostics (scripts/verify_setup.py)
make train
make inspect   # voice + text Inspector
```

Run `make` alone for the grouped help screen.

## Ground rules

- Reference secrets only as env vars / `.env` — never commit keys
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs)
- Never let a skill state a car, price, dealer, or availability that did not
  come from a tool result
- Keep each skill focused; compose with `@skill.<name>` when needed
- Prefer progressive control: prose → tool constraints → scoped `if:` →
  verbatim `utter:` → ordered blocks only when order is the requirement

## Memory scoping gotcha

A bare entry name declared in a skill's `memory.yml` **shadows** the project
field of the same name, so a tool writing that name lands in the skill scope.
`finalize_reservation` deliberately writes `car_model`, `car_price`, and
`dealer_name`, and no skill declares those names — that is what lets
`schedule_dealer_appointment` and `calculate_loan` pick the reservation up.
`reserve_car` uses `selected_model` / `selected_dealer` / `selected_price` for
its own working state to avoid shadowing them.

Docs for authors: see `tutorial/TUTORIAL.md` and `.cursor/rules/rasa-skills.mdc`
