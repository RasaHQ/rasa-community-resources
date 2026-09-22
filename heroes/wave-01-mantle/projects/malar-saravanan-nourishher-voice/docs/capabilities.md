# NourishHer — what the app can do 

A **voice-first women's health nutrition companion** built on Rasa Mantle. It
holds a natural conversation, remembers you across turns, and grounds every
number in a real tool result — no invented data.

Architecture at a glance: [`diagrams/nourishher-capabilities.drawio`](diagrams/nourishher-capabilities.drawio)
(open at [app.diagrams.net](https://app.diagrams.net) or the draw.io VS Code
extension).

---

## What it can do

- **Onboard & remember** — captures your name, goals, food preferences,
  allergies, and (optional) health conditions, and reuses them every session.
- **Log meals naturally** — "I had oatmeal and a banana" → structured log entry.
- **Plan meals & grocery lists** — generates a plan for your constraints and a
  shopping list, and can recall a saved plan by date.
- **Recall history & coach** — "what did I eat today?", behavioural summaries,
  gentle habit coaching.
- **Answer nutrition questions with real data** — e.g. protein in 100 g chicken,
  returned as a macro/micro table with %DV from the **live USDA** database.
- **Optional condition-aware guidance** — PCOS, hypothyroidism, type-2 diabetes,
  fertility/preconception — grounded in curated guideline snippets (RAG). Health
  context is never required.
- **Safety first** — detects red flags (possible hypoglycemia, disordered-eating
  signals, medication/diagnosis requests, urgent symptoms) and escalates; never
  diagnoses, never gives medication or dosage advice.
- **Voice or text** — Deepgram ASR/TTS, plus a browser text/voice demo UI.

## The agent & its skills

One agent — **NourishHer** (`agent.yml`: persona + safety rules) — composed of
**16 skills**:

| Group | Skills |
|---|---|
| Onboarding | `intro`, `intake_profile`, `update_profile` |
| Everyday nutrition | `meal_logging`, `meal_planning`, `meal_history`, `nutrition_qna`, `coaching_checkin` |
| Condition-aware (optional) | `pcos_nutrition`, `hypothyroidism_nutrition`, `diabetes_nutrition`, `fertility_nutrition`, `hypothyroidism_reminder_gate` |
| Safety & care | `safety_escalation`, `professional_referral`, `goodbye` |

## Tools that support it (15, all deterministic)

- **Profile:** `save_user_name`, `save_health_profile`, `get_user_profile`,
  `update_user_profile`, `delete_user_profile`
- **Meals & plans:** `log_meal`, `log_symptom`, `get_meal_history`,
  `get_behavioral_summary`, `create_meal_plan`, `get_saved_plan`,
  `create_grocery_list`
- **Nutrition facts:** `get_food_nutrient_info` → live USDA FoodData Central
- **Safety:** `send_levothyroxine_reminder_if_needed` (verbatim),
  `request_professional_referral`

## Memory & persistence

Two layers, both real (no mocking):

- **File-backed per-user store** (`lib/store.py`, atomic writes, under `data/`):
  - `profiles/<user>.json` — name, goals, cuisine/diet, likes/dislikes, and later edits
  - `meal_logs/<user>.jsonl` — append-only meal & symptom log
  - `meal_plans/<user>.json` — saved plans by date
- **Project memory** (`session.project.*`) — condition flags plus the meds and
  allergies lists captured at intake; **write-once per field per session**.
  Skills' `requires:` can read only these, which is why the freely-editable
  profile and all append-only history live in the file store instead.

## LLM-driven vs deterministic

| Layer | LLM-driven? | Why |
|---|---|---|
| Routing / skill activation | ✅ LLM | orchestrator decides which skill fits |
| Natural-language replies (persona) | ✅ LLM | every user-facing sentence |
| Field extraction (`intro`, `intake_profile`) | ✅ LLM | fills `llm_settable` fields from speech |
| `nutrition_qna` + 4 condition skills | ✅ LLM + RAG | Gemini embeddings + FAISS over guideline docs |
| `meal_planning`, `coaching_checkin` | ✅ LLM | generates the plan / coaching |
| Safety red-flag detection | ✅ LLM | recognizes the risk in free text |
| **All `@tool` functions** | ❌ deterministic | pure Python, same input → same output |
| **File store / project memory** | ❌ deterministic | JSON/JSONL I/O, atomic writes |
| **USDA lookup** | ❌ deterministic | HTTP call, real numbers |
| **Verbatim reminders, field validation** | ❌ deterministic | fixed text / rules |

> Rule of thumb: **the LLM understands, routes, and phrases; the tools and store
> do the real work and own every fact, number, and record.** The deterministic
> layer is covered by `make test` (9 tests, no network/LLM).

## Providers

- **LLM (orchestrator):** OpenAI `gpt-4o` primary, Groq `gpt-oss-120b` fallback
  only (weighted router in `integrations.yml`; Groq never load-balanced in).
- **Embeddings (RAG):** Gemini · **Voice:** Deepgram · **Nutrition:** USDA.
- Pinned to **`rasa-pro 3.20.0.dev6`** (frozen wave-01-mantle snapshot).
