# Mantle features — used & TODO

What of the Rasa Mantle engine this project actually exercises, how, and what is
still open.

## Used

| Feature | How we use it |
|---|---|
| Skills as `skill.md` units | 16 skills, each with `name` / `description` / natural-language instructions — no hand-written stories |
| LLM flow orchestration & routing | Orchestrator activates skills from their descriptions; handles digressions/interruptions (conversation stack grows mid-turn) |
| `requires:` conditional activation | e.g. `pcos_nutrition` → `requires: session.project.profile_intake_complete == True and session.project.has_pcos == True` |
| Tools (`@tool`) + `import_tools:` | 15 tools; per-skill imports plus shared tools — the LLM calls them, they own the facts |
| `tool_constraints:` | `save_health_profile` gated on `requires: session.intake_profile.summary_confirmed`, `on_success: utter_profile_saved` |
| Memory (skill-scoped + project) | `llm_settable` fields in `session.<skill>.*`; condition flags in write-once `session.project.*` |
| Ordered blocks | `:::ordered_block id=collect_profile` + `@block.collect_profile` for structured multi-step onboarding |
| Skill handoff | Rules hand off to `@skill.safety_escalation` on safety red flags |
| References / RAG | `references:` + a separate embeddings model group (Gemini) + FAISS index over condition guideline docs |
| Persona + safety rules | `agent.yml` persona and 7 global top-level `rules` as guardrails |
| Voice | `voice: asr/tts` → Deepgram ASR + TTS |
| Model groups | `orchestrator_llm` (OpenAI primary, Groq fallback-only via a weighted LiteLLM router) and `reference_embeddings` (Gemini) |
| Contextual response rephraser | `endpoints.yml` rephraser on Gemini — natural-sounding voice replies |
| Verbatim vs rephrased responses | `responses.yml` + the verbatim levothyroxine safety reminder |
| e2e eval harness (`rasa test e2e`) | `tests/e2e_test_cases.yml` (4 assertion-based cases) + `make e2e` / `make e2e-coverage`; structural (`flow_started`) + response-text (`bot_uttered`) assertions. **4/4 pass** on the live OpenAI-primary orchestrator: greeting, meal logging, nutrition lookup (routes to `nutrition_qna` and grounds the reply in a real USDA tool call), safety escalation |
| Tracing / observability | OTLP tracing + SQL tracker_store wired in `endpoints.yml` (opt-in; env-gated endpoint) |

## TODO

| Feature | TODO |
|---|---|
| Condition-skill routing (e2e) | Not automatable via fixtures: condition skills gate on `session.project.*` (slots named `project.<entry>`), and the e2e fixture schema rejects dotted keys — those flags are only written by completing `intake_profile`. Documented as a manual/conversational check in `tests/e2e_test_cases.yml` |
| `generative_response_is_grounded` assertions | Documented in the suite; enable once an LLM judge is configured + a reliable provider is set |
| Levothyroxine reminder (Bug 7) | Not automatable via fixtures (same `session.project.*` limitation as condition-skill routing above) — no e2e case exists for it; verify it live, conversationally, on a reliable provider |
| Enable tracing in prod | Uncomment the `endpoints.yml` tracing block and point it at a collector |
