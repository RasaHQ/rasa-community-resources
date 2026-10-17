# Rasa Skills project — NourishHer voice nutrition companion

This directory is a **Rasa Skills / Mantle** agent: **NourishHer**, a
voice-first women's health nutrition companion. It is a *general*
everyday-nutrition coach — onboarding/profile, goals, meal planning, natural
meal logging, meal history, coaching, and general Q&A — with **optional**
condition-aware support (hypothyroidism, PCOS, type 2 diabetes,
fertility/preconception). Health context is never required. It evolved in
place from the earlier condition-only "Sage" build.

No mocking: it is production-grade. Every specific-food number is backed by a
real `get_food_nutrient_info` (USDA FoodData Central) call rendered as
separate macro/micro tables (amount + %daily-value, "per 100 g" basis
stated). Profile, meal logs, and saved plans persist in a real file-backed,
per-user store (`lib/store.py`, under `data/`). Nothing is seeded or
fabricated. Lifestyle/activity guidance stays general and non-prescriptive,
same safety bar as the food guidance.

Pin: `rasa-pro==3.20.0.dev6` — the latest release on PyPI as of this build,
past the CALM-era → Mantle engine rename (`rasa.calm_v2.*` →
`rasa.mantle.tools.*`, CLI `--engine` now `mantle`). This project started on
`3.19.0.dev5` (pre-Mantle) and was migrated forward — see the "Known open
issues" section of `README.md` for what that migration required and
what's still open. LLM: OpenAI `gpt-4o` (primary), Groq
`groq/openai/gpt-oss-120b` (fallback only, via a weighted LiteLLM router — see
`integrations.yml`). Embeddings: Gemini.
Scaffold pattern originally copied from the flagship Atlas tutorial project,
`examples/mantle-voice-agent`.

## Layout

- `agent.yml` — identity, persona (NourishHer), voice flags, rules, `references:`
- `integrations.yml` — OpenAI/Groq LLM router + Inspector channel with Deepgram ASR/TTS
- `endpoints.yml` — optional platform services (response rephraser, tracing)
- `memory.yml` — project-wide memory (condition flags, meds, allergies, log)
- `responses.yml` — project-wide verbatim/rephrased responses
- `skills/<name>/` — one skill per folder (`skill.md`, optional `tools.py`,
  `memory.yml`, `responses.yml`, `references/`)
- `tools/` — **shared** `@tool` functions: `nutrition.py`
  (`get_food_nutrient_info`), `profile.py` (`get_user_profile`,
  `update_user_profile`, `delete_user_profile`), `meals.py` (`log_meal`,
  `log_symptom`, `get_meal_history`, `get_behavioral_summary`,
  `create_meal_plan`, `get_saved_plan`, `create_grocery_list`,
  `request_professional_referral`)
- `lib/` — shared Python helpers: `usda_client.py` (USDA FoodData Central),
  `store.py` (real file-backed per-user profile/log/plan persistence)
- `data/` — runtime per-user data (`profiles/`, `meal_logs/`, `meal_plans/`),
  git-ignored; never committed
- `tests/` — deterministic `unittest` suite over the store + tools
  (`make test`, no LLM/network)
- `ui/` — self-contained embedded web chat UI (`index.html`), voice-capable
  via the browser Web Speech API, talks to the REST channel; served by
  `make ui`, backed by `make api` (CORS-enabled). Keys a stable per-user id
  in localStorage matching the backend's per-sender file store.
- `scripts/` — `verify_setup.py`, `validate_project.py`

## Skills

**General companion (all users, no condition required):**

- `intro` — greeting/orientation, captures preferred name
- `intake_profile` — full onboarding: name, goal (plain language),
  cuisine/region, diet, likes/dislikes, cooking time, budget, allergies, and
  an **optional** health-context block (the four conditions). Ordered-block
  with a read-back confirmation. Rich prefs write to the file store as they're
  learned; condition flags stage → project memory on save.
- `update_profile` — one-off add/change/remove of a stored preference
  (`update_user_profile` / `delete_user_profile`) without re-running intake
- `meal_planning` — profile-grounded meal suggestions (1 primary + 1 alt),
  plus save-plan / recall-plan / grocery-list
- `meal_logging` — natural/approximate meal logging + feeling notes
  (`log_meal`, `log_symptom`)
- `meal_history` — recent-history retrieval and cautious summaries
  (`get_meal_history`, `get_behavioral_summary`)
- `coaching_checkin` — supportive, non-judgmental coaching + next step
- `nutrition_qna` — general nutrition questions, safety-aware
- `professional_referral` — route to clinician/dietitian/pharmacist/urgent
  care and record it (`request_professional_referral`)
- `safety_escalation` — hard, verbatim red-flag hand-off. Types:
  hypoglycemia, thyroid_crisis, menstrual_pattern, disordered_eating,
  medication_change, diagnosis_request, cure_claim, urgent_symptom, other —
  never LLM-generated
- `goodbye` — closing

**Optional condition-specific guidance (gated on the matching flag):**

- `hypothyroidism_reminder_gate` — blocks-only skill (no prose) that exists
  purely to force the levothyroxine reminder's `execute_tool` step as the
  flow's deterministic first step, then `link:`s into
  `hypothyroidism_nutrition` in the same turn. Workaround for Bug 7 (a plain
  `utter: on: activate` trigger did not fire reliably) — see
  `docs/diagrams/nourishher-architecture.drawio` for where this fits in the
  overall flow.
- `hypothyroidism_nutrition` (flagship) — thyroid-aware meal guidance;
  `requires:` only allows it once the reminder gate above isn't needed
- `pcos_nutrition`, `diabetes_nutrition`, `fertility_nutrition` — the same
  pattern for the other three conditions, each gated on its own condition
  flag via a skill-level `requires:`

## Tool placement

- Default: put tools in `skills/<name>/tools.py` (auto-discovered).
- Shared (`tools/` at the agent root) when two or more skills need the same
  function — `get_food_nutrient_info` (USDA), the profile tools, and the meal
  tools are all shared across the general skills.
- Imports:

```python
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
```

## Real data, not seeded demo data

There is no mock database. The "real data" is:
- The person's own profile. Condition flags persist via project `memory.yml`
  (they gate skills); the richer, freely-mutable preferences (name, cuisine,
  diet, likes/dislikes, cooking time, budget, goals, health context) persist
  in a real file-backed per-user store, `data/profiles/<sender>.json`
  (`lib/store.py`) — not a fabricated dataset.
- Live macro/micro nutrient lookups from the USDA FoodData Central API
  (`lib/usda_client.py`), a free public API. %Daily-value is computed in
  code from the FDA's own published adult general-population Daily Values
  (`DAILY_VALUES` in that file) — a real reference table, not an LLM guess.
- Meal ideas are composed by the LLM from the person's real stored profile
  and validated against real USDA lookups when specific numbers are cited —
  never invented recipes or nutrient figures.
- Published condition-specific dietary guidance baked into each skill's
  `references/*.md` as grounding text for the `references:` retrieval
  mechanism (not treated as real-time data).
- The person's own meal/symptom log and saved plans, in
  `data/meal_logs/<sender>.jsonl` and `data/meal_plans/<sender>.json`
  (atomic writes) — a real local data store, keyed per sender id so multiple
  users (and the five documented test profiles) stay isolated.

## Build loop

```bash
make install
make env
make verify
make validate
make test
make train
make inspect
```

## Ground rules

- Skills live under `skills/<name>/` as `skill.md` files with optional
  `tools.py`, `references/`, `memory.yml`, and `responses.yml`.
- Progressive control levers: skill-level `requires:`, `tool_constraints`
  (`requires`, `requires_confirmation`), `if:` markers, `utter:` (with
  `on:`/`when:`), `:::ordered_block`, `@skill.<name>`.
- Every condition is an expression string with fully namespaced memory
  (`session.intake_profile.summary_confirmed`, `session.project.has_pcos`),
  never a mapping.
- Skill `memory.yml` uses a `schema:` root key and `text` (not `string`)
  types; project-root `memory.yml` uses plain top-level keys (no `schema:`).
- Project-scope fields (`session.project.*`) are written by tools via
  `context.memory.set(...)`, not set directly by the LLM — skills collect
  raw answers in their own skill-scoped memory first, then a tool copies
  the confirmed values into project scope. This mirrors the reference
  project's `get_booking` → `selected_booking_ref` pattern.
- **Project memory is write-once per field per session, and the check is
  "is the current value non-`None`" — not "has this been written before."**
  Never give a project `memory.yml` field a non-null `initial_value`
  (`false`, `""`, an enum member, ...) if a tool needs to write it, or every
  write fails immediately (the field looks "already set" from turn one).
  A field that needs more than one write per session (a running log, a
  counter, ...) cannot use project memory at all — write to the file-backed
  store instead (`lib/store.py`, used by the profile and meal tools). A field
  that might legitimately need a same-session correction should catch
  `rasa.mantle.memory.manager.ProjectMemoryAlreadySetError` per write and
  degrade gracefully (see `skills/intake_profile/tools.py`).
- Escalation and medication-timing responses never carry
  `metadata.rephrase: true` — exact wording every time, by design.
- Do **not** add CALM v1 files (`domain.yml`, `config.yml`, flow YAMLs).
- Reference secrets only as env vars / `.env` — never commit keys.
- Voice instructions must be short sentences suitable for TTS.
- This assistant never diagnoses, never adjusts medication or dosage — see
  the persona and rules in `agent.yml`.
- After changing a skill, run `make validate` and `make test`, then
  `make train` and `make inspect`.
