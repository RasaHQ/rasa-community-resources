# NourishHer — Glossary & Orientation

Read this first if you're reviewing [`dev-doc.md`](dev-doc.md) or
[`feedback-log.md`](feedback-log.md) and aren't deep in this codebase or in Rasa
Mantle. It explains, in plain language, every **file**, **framework term**, and
**project variable** those docs mention.

## The app in three sentences
NourishHer is a voice-first nutrition companion built on **Rasa Pro (Mantle)** —
Rasa's LLM-driven assistant framework. A user chats (or speaks) through a small
web page; the Mantle engine decides which "skill" should handle each message and
calls Python "tools" to look things up or save data. Real data comes from the
USDA nutrition API, an embeddings-based knowledge base, and per-user files on disk.

---

## 1. Repo files & folders (what each one is)

| Path | Plain-language purpose |
|---|---|
| `agent.yml` | The assistant's identity: name, persona, global rules, voice on/off, and the RAG/`references` + `tool_timeout` settings. |
| `integrations.yml` | Which **LLM providers** power the assistant, and which **channels** it's reachable on (web REST + the Rasa Inspector with Deepgram voice). |
| `endpoints.yml` | Runtime services — most relevant here, the **response rephraser** LLM. |
| `memory.yml` (repo root) | **Project-wide memory** fields shared across all skills (e.g. the user's condition flags). |
| `responses.yml` (repo root) | Project-wide **fixed bot responses** (greeting, fallback, etc.). |
| `skills/<name>/skill.md` | One **skill** = one capability. Prose instructions for the LLM + a config header (front-matter). |
| `skills/<name>/memory.yml` | Memory fields **owned by that one skill** (temporary, per-conversation). |
| `skills/<name>/responses.yml` | Fixed responses owned by that skill. |
| `skills/<name>/tools.py` | Python **tools** used only by that skill. |
| `skills/<name>/references/*.md` | Knowledge documents that skill can retrieve from (the RAG source). |
| `tools/` | **Shared tools** used by several skills: `nutrition.py` (USDA lookup), `profile.py` (profile read/write), `meals.py` (logging, history, plans). |
| `lib/store.py` | Our **file-backed database**: reads/writes per-user JSON/JSONL under `data/`. |
| `lib/usda_client.py` | Client for the live **USDA FoodData Central** nutrient API. |
| `data/profiles/`, `data/meal_logs/`, `data/meal_plans/` | The actual saved per-user data (one file per user, keyed by their conversation id). |
| `ui/index.html` | The embedded **web chat UI** (voice + text) that talks to the assistant. |
| `tests/` | Automated tests for the store + tools (`make test`); no LLM/network needed. |
| `Makefile` | Shortcut commands: `make validate | test | train | inspect | api | ui`. |

---

## 2. Rasa Mantle terms (framework concepts the docs use)

| Term | Plain-language meaning |
|---|---|
| **Skill** | A single capability the assistant can perform (e.g. "log a meal"), defined by a `skill.md`. The engine routes each user message to one skill. |
| **Orchestrator** | The Mantle engine that reads the message, picks a skill, and runs the "call a tool → get result → decide next" loop for the turn. |
| **Turn** | One user message and the assistant's full response to it (which may involve several tool calls and even more than one skill). |
| **Tool** (`@tool`) | A Python function the LLM is allowed to call to do real work — look up nutrition data, save a profile, etc. |
| **`ToolContext`** | An object passed into every tool giving it access to memory, the ability to send an interim message (`context.send`), and a cancel check (`context.is_cancelled`). |
| **`ToolResult(llm_response=…)`** | What a tool returns; the `llm_response` dict is the data handed back to the LLM. |
| **Project memory** (`session.project.*`) | Durable memory shared across skills for the whole conversation. In this Mantle version it is **write-once per field per session** (see §3 "write-once"). |
| **Skill memory** (`session.<skill>.*`) | Temporary memory owned by one skill. `llm_settable: true` lets the LLM fill a field during conversation. |
| **`import_tools`** | A line in a `skill.md` header declaring which shared tools that skill may call. |
| **`tool_constraints`** | Rules on a tool: `requires:` hides it until a condition is met; `on_success:` fires a response after it runs. |
| **`:::ordered_block`** | A deterministic, engine-run sequence of steps inside a skill (used for step-by-step intake). |
| **`complete_when`** | The condition that marks an ordered-block step (or a skill) finished. |
| **`execute_tool` / `link`** | Ordered-block step types: run a specific tool / hand off to another skill mid-turn. |
| **`requires:`** (skill-level) | A boolean condition deciding whether a skill is even allowed to activate. |
| **`utter: on/when`** | Attach a fixed response to a skill, optionally chosen by a memory value. |
| **`metadata.rephrase: true`** | Allows a fixed response to be reworded by the rephraser. **Omitting it = spoken verbatim** (used for safety messages). |
| **`references` / RAG** | "Retrieval-augmented generation" — the assistant retrieves relevant reference docs (via embeddings) to ground its answer. |
| **Rephraser (NLG)** | A separate LLM that lightly rewords fixed responses so they don't sound canned. |
| **`model_group`** | A named LLM/embeddings configuration that a role points to (orchestrator vs rephraser vs embeddings). |
| **`ProjectMemoryAlreadySetError`** | The error raised if a tool tries to write a project-memory field that's already set this session. |
| **Inspector** | Rasa's built-in browser tool for talking to the assistant (uses Deepgram for voice). Separate from our custom `ui/`. |

---

## 3. Project-specific variables (memory fields you'll see quoted)

**Project memory (`session.project.*`) — the durable, cross-skill flags:**

| Field | Meaning |
|---|---|
| `user_first_name` | What the user likes to be called. |
| `profile_intake_complete` | Has the profile been collected & confirmed at least once? |
| `has_hypothyroidism` / `has_pcos` / `has_type2_diabetes` / `has_fertility_focus` | Whether the user reported each condition (these **gate** the optional condition skills). |
| `hypothyroidism_status` / `pcos_status` / `diabetes_status` / `fertility_status` | The status enum for each (e.g. `confirmed` / `suspected` / `not_applicable`). |
| `takes_levothyroxine` | Whether the user takes thyroid medication (drives the timing reminder). |
| `levothyroxine_reminder_sent` | Whether the one-time medication-timing reminder already played this session. |
| `meds_list` / `allergies_list` | Free-text medications and allergies. |

**Skill memory (examples) — temporary, owned by a skill:**

| Field | Meaning |
|---|---|
| `session.intake_profile.summary_confirmed` | User confirmed the read-back profile summary. |
| `session.intake_profile.*_captured` / `*_asked` | Progress flags for each step of the intake block. |
| `session.safety_escalation.escalation_type` | Which red-flag category triggered a safety hand-off. |

**Shared tools (in `tools/`), by job:**

| Tool | What it does |
|---|---|
| `get_user_profile` / `update_user_profile` / `delete_user_profile` | Read / change / remove the user's stored profile (in `data/profiles/`). |
| `log_meal` / `log_symptom` | Save what the user ate / how they felt (`data/meal_logs/`). |
| `get_meal_history` / `get_behavioral_summary` | Read back recent logs / simple patterns. |
| `create_meal_plan` / `get_saved_plan` / `create_grocery_list` | Save, recall, and derive a shopping list from a meal plan (`data/meal_plans/`). |
| `get_food_nutrient_info` | Live macro/micro nutrient lookup from the USDA API. |
| `request_professional_referral` | Record that the user should see a clinician/dietitian/etc. |

---

## 4. Provider/model names you'll see

| Name | Role here |
|---|---|
| **OpenAI — `gpt-4o`** | The orchestrator LLM (routing + tool-calling), run at temperature 0 for precision. Primary — serves every turn while healthy. |
| **Groq — `gpt-oss-120b`** | Fallback orchestrator LLM only, via a weighted router (`integrations.yml`) — never load-balanced against OpenAI, used only when it fails or is cooling down. |
| **Gemini — `gemini-flash-latest`** | The rephraser LLM (temperature 0.7, for natural wording). |
| **Gemini — `gemini-embedding-001`** | Embeddings for the RAG knowledge base. |
| **Deepgram** | Speech-to-text + text-to-speech for the Rasa Inspector's voice path. |
| **USDA FoodData Central** | The live nutrition database behind `get_food_nutrient_info`. |
