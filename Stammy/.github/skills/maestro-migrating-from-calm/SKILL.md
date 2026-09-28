---
name: maestro-migrating-from-calm
description: >
  Migrates a CALM (flows-based) Rasa assistant to the Maestro engine: maps flows to
  skills, slots to memory, custom actions to tools, and identifies what has no
  migration path (custom components, command generators, NLU pipeline, rephraser
  customizations). Use when a project contains domain.yml/config.yml/flows and the
  goal is a Maestro agent.
license: Apache-2.0
engine: maestro
rasa_version: ">=3.18"
metadata:
  author: rasa
  version: "0.1.4"
  docs-url: https://rasa-2f7eb63d.mintlify.site
---

# Migrating a CALM assistant to Maestro

Maestro is not a config translation — it's a different control model. CALM encodes
behavior as explicit flow steps; Maestro encodes it as prose instructions plus
targeted control levers. A mechanical 1:1 port of every flow step into an ordered
block produces the worst of both worlds. Migrate *intent*, not *structure*.

Target the config shapes the other skills document: an `agent.yml` with an
`agent:` block carrying `persona`, and `rules` / `prompts` / `session_config` as
top-level siblings of it; a flat `integrations.yml` `llm:` block plus `channels:`;
`memory.yml` `schema:` with every written key declared; one `tools.py` per skill;
and the `rasa train` then `rasa inspect` loop. The engine is selected by project
layout, so there is no version key to set.

## Migration workflow

1. **Inventory** the source project: flows (`data/`), slots + responses
   (`domain.yml`), custom actions (`actions.py` / action server), pipeline
   customizations (`config.yml`), endpoints/credentials.
2. **Group flows into skills.** One skill per user goal. A CALM parent flow with
   its `call`ed child flows usually collapses into ONE skill — child flows become
   prose sections, `@block`s, or sub-skills only if independently reusable.
3. **Port tools first** (from custom actions) — they're the most mechanical part
   and everything else references them.
4. **Rewrite each flow as prose** in `skill.md`: describe the goal and what to
   gather, not step numbering. Let the LLM own sequencing initially.
5. **Re-add guarantees the old flow actually enforced** using the control ladder
   (see `maestro-building-skills`): slot preconditions become `requires:`, branching
   becomes one `if:` marker per case, confirmations become prose plus a confirmation
   memory key gated with `requires:`, mandated wording becomes verbatim `utter:`
   responses, and genuinely order-critical sections become one ordered block. For an
   irreversible tool call, `requires_confirmation:` plus `on_success:` /
   `on_failure:` in `tool_constraints` lets the engine pause and emit fixed outcome
   text instead of relying on prose.
6. **Port config** to `agent.yml` + `integrations.yml` (see
   `maestro-configuring-agent`).
7. **Test side by side**: run the same conversations against the old bot and the
   new agent (`rasa inspect`); compare outcomes per the checklist in
   `maestro-testing-debugging`.

## Mapping table

| CALM artifact | Maestro target | Effort |
|---|---|---|
| Flow (YAML steps) | Skill prose body; ordered block only for order-critical sections | Rewrite, not transform |
| `call` step → child flow | Same-skill prose section or `@block.<block_id>`; `@skill.<skill_id>` if reused across skills | Judgment call |
| `link` step | `@skill.<skill_id>` reference, or plain orchestrator routing | Small |
| `collect` step | Prose ("ask for X"); `collect:` step inside an ordered block if strict | Small |
| Slot | Memory entry in `memory.yml` `schema:` — `public` if other skills read it, else `private`; categorical slots keep their values as `enum_values` | Small |
| Slot validation action | `run_after_setting_<memory_entry>` tool in the same `tools.py`; return a non-null `error` to reject and roll back the write | Small |
| Dynamic question generation | Prose ask, or `instructions:` + `complete_when:` on an ordered-block step | Small |
| `utter_` response (must stay exact) | `responses.yml` + `utter:` triggers | Small |
| `utter_` response (tone only) | Delete — prose instructions + persona cover it | Free |
| Custom action | `@tool` function in the skill's `tools.py` (import `tool`/`ToolContext`/`ToolResult` from `rasa.calm_v2.tools.*`, not `rasa_sdk`): `tracker.get_slot` → `context.memory.get`, `SlotSet(...)` → `context.memory.set(...)`, `dispatcher.utter_message` → `context.send` or `llm_response` | Medium — code updates + verification |
| `pattern_session_start` | The bundled `default_session_start` skill's `utter_greet`; redeclare it in your project `responses.yml` to change the wording | Small |
| Rephraser prompt | `agent.yml` `agent.persona` | Small |
| `credentials.yml`, `endpoints.yml` model/LLM config | `integrations.yml` (`llm` + `channels`) | Small |
| `endpoints.yml` Langfuse `tracing:` | `integrations.yml` `tracing:` (`type: langfuse`) | Small |
| `domain.yml` | Dissolves — slots→memory, responses→responses.yml/prose, actions→tools | Structural |

## No migration path — flag these to the user, do not silently drop

| CALM artifact | Why it breaks | What to do |
|---|---|---|
| Custom graph components (`config.yml` pipeline) | The pipeline doesn't exist; one LLM loop replaced it | Identify the component's *intent*; check if a control lever or tool covers it; otherwise raise to the user |
| Custom command generators | The command-generation stage is gone | Usually subsumed by the orchestrator; verify the behaviors it enforced, re-add as levers |
| NLU pipeline tuning (intents, entities, regexes) | No NLU stage | Intent triggers → skill `description` phrasing; entity extraction → tool arguments typed by the LLM |
| Standalone rephraser customizations | Stage removed; phrasing is inline | Global tone → `persona`; per-response mandates → verbatim responses |
| ReAct-style sub-agents | Subsumed by the single orchestrator | Re-express as skills; reach an external agent from inside a tool |

## Anti-patterns

- **The 40-step ordered block.** If the migrated skill is one giant block mirroring
  the old flow graph, you've rebuilt the state machine. Ask which steps had a
  *regulatory or correctness* ordering requirement — typically 2-5 — and let prose
  handle the rest.
- **A slot-for-slot memory schema.** CALM projects accumulate bookkeeping slots
  (flow guards, internal flags). Most become unnecessary — the framework tracks
  block step state and skill routing itself. Port only memory that carries business
  meaning.
- **Porting `utter_` responses wholesale into responses.yml.** Verbatim responses
  are for wording that MUST be exact. Porting all 200 utterances makes the agent
  sound like the old bot and defeats the engine. Default to deletion; keep the
  legal/compliance set.
- **Migrating all flows at once.** Port one high-traffic skill end to end, validate
  behavior parity, then batch the rest with the patterns you established.

## Verification of parity

For each migrated skill, run the old bot's e2e test conversations manually against
the new agent and confirm: same data collected, same gates enforced (confirmations,
auth), same side effects (tool calls that hit real APIs), compliance wording
byte-identical where required. Log every intentional behavior difference in the
migration notes for the user — "more natural" is a change too.

## Further reading

Full Maestro documentation: https://rasa-2f7eb63d.mintlify.site

Fetch `https://rasa-2f7eb63d.mintlify.site/llms.txt` for the page index, or
`https://rasa-2f7eb63d.mintlify.site/llms-full.txt` for every page in one file.
Read the specific page when this file is not enough; do not guess syntax.

Most relevant here:

- [Project structure](https://rasa-2f7eb63d.mintlify.site/reference/project-structure): the Maestro layout a CALM project maps onto
- [skill.md reference](https://rasa-2f7eb63d.mintlify.site/reference/skill-md): what a flow becomes
- [memory.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/memory-yml): what a slot becomes
- [Tools reference](https://rasa-2f7eb63d.mintlify.site/reference/tools): what a custom action becomes
- [Conditions](https://rasa-2f7eb63d.mintlify.site/reference/conditions): the expression grammar replacing flow conditions
