---
name: maestro-testing-debugging
description: >
  Tests and debugs Maestro agents: the train → converse loop, reading
  memory and tool activity in the inspector, and mapping observed misbehavior to the
  control lever that fixes it. Use after any change to skills or config, when the
  agent misbehaves in conversation, or when train fails.
license: Apache-2.0
engine: maestro
rasa_version: ">=3.18"
metadata:
  author: rasa
  version: "0.1.3"
  docs-url: https://rasa-2f7eb63d.mintlify.site
---

# Testing and debugging a Maestro agent

## The loop

Run after every meaningful edit — it's fast and catches drift early:

```bash
rasa train             # validates and compiles the project into a model
rasa inspect           # browser UI: converse + watch memory/tools live
```

- Fix `rasa train` errors before debugging conversation behavior: it is the
  validation gate for the whole project. `rasa data validate` runs the same
  Maestro project validation without training, which is faster when you only want
  to check config and skills.
- Prefer `rasa inspect` over `rasa shell` for debugging: it shows memory state,
  active skill, and tool calls per turn. Known beta quirk: `rasa shell` prints the
  welcome message only after the first user input — not a bug in your agent.
- Retrain after ANY change to `skill.md`, `memory.yml`, `responses.yml`,
  `agent.yml`, or `integrations.yml`. Tool body changes in `tools.py` also require
  retraining if signatures/decorators changed.

## Test conversations to run every time

For each skill, walk at minimum:

1. **Happy path** — the goal completes end to end.
2. **Out-of-order user** — give information before being asked ("I lost my card,
   the gold one, send it rush"). The agent should absorb it, not re-ask.
3. **Digression** — switch to another skill mid-way, then return. The original
   skill should resume where it left off.
4. **Correction** — change an earlier answer ("actually it was stolen, not lost").
   Memory should update and branch-scoped instructions should re-scope.
5. **Refusal/uncertainty** — decline a confirmation. Gated tools must NOT fire.
6. **Out of scope** — ask something no skill covers. The agent should say so
   gracefully, not hallucinate a capability.

## Symptom → fix table

Behavioral drift is fixed with control levers (see `maestro-building-skills`), not
by rewriting prose louder. Find the symptom, apply the narrowest fix:

| Symptom | Diagnosis | Fix |
|---|---|---|
| Tool called before its inputs exist | Tool visible too early | `tool_constraints` → `requires:` on the missing memory key |
| Irreversible action without asking | No confirmation before the tool | In-flow prose + `requires:` on a confirmation key, or `requires_confirmation:` on the tool |
| Tool ran but mandated success/failure wording missing | Outcome utter not wired | `on_success:` / `on_failure:` on the tool + `responses.yml` templates |
| Wrong workflow branch followed / branches blended | All branches visible in prompt | one `if:` marker per case, each stating its own condition |
| Compliance/legal wording paraphrased | LLM generating what must be verbatim | `utter:` trigger + `responses.yml` |
| Steps skipped/reordered where order is the requirement | Prose can't enforce sequence | ordered block for that section (`@block.<id>`), keep the rest prose |
| Skill activates when it shouldn't | Routing on description alone | sharpen `description`; add skill-level `requires:` |
| Skill doesn't activate when it should | Description doesn't match user phrasing | add trigger phrasings to `description` |
| Agent re-asks for known information | Value never landed in memory | tool must `context.memory.set(key, value)`; check the inspector memory panel |
| Sub-skill runs but parent loses the result | Result declared `private` | move the entry to `public` in the sub-skill's `memory.yml` |
| Gated tool never becomes available | `requires:` key never written, or name mismatch | compare the exact key in the constraint vs what the tool sets |
| Tool confirmation ask never appears | `enabled` not true, `utter_for_confirmation` missing/empty in `responses.yml`, blank after placeholder resolution, or tool still gated | check train validation; inspect substituted ask text in the turn |
| Tool re-called while confirmation pending | Model tried to run the gated tool again instead of resolving | call `resolve_tool_confirmation` with `confirmed=true` or `false`; re-call is rejected |
| `rasa train` fails with `undeclared_memory_write` | Tool writes a key not in any `memory.yml` schema | declare the key (with its `type`) in the skill or project `memory.yml` |

`requires_confirmation:`, `on_success:`, and `on_failure:` are supported on
`tool_constraints`. Skill `utter:` triggers (`on: activate`, structured `when:`)
emit other fixed templates — see `maestro-building-skills`.

## Debugging tool failures

- Tool missing from the LLM's list: it's gated by an unmet `requires:` (intended),
  the function isn't in the skill's `tools.py`, or a shared tool from the agent-root
  `tools/` folder wasn't declared in `import_tools`. A skill-local tool shadows a
  shared tool of the same name, resolved once at model load.
- Tool missing after a knowledge search: once `search_knowledge` has run in a turn,
  the skill's own tools are withheld for the rest of that turn and return on the
  next one. Not a gating problem.
- Tool crashes: run `rasa inspect` from a terminal and watch the server log. Tool
  tracebacks appear there, not in the browser.
- Memory write rejected: the key isn't declared in the skill's (or project's)
  `memory.yml` schema — `rasa train` flags it as `undeclared_memory_write`.
  Declare the key with its `type` and retrain.

## Training failures

`rasa train` errors name the file. Fix in this order, because later files
reference earlier ones: `integrations.yml`, `agent.yml`, each skill's
`memory.yml` / `responses.yml`, then `skill.md`.

Frequent causes:

- a `tool_constraints`, `utter:`, `action:`, or `utterance:` entry naming a tool or
  response that doesn't exist
- a `requires:` written as a map instead of a string expression
- a condition using a bare memory key instead of
  `session.<skill_id>.<entry>` or `session.project.<entry>`
- an `@memory.…` token in instruction prose naming unreadable memory, an incomplete
  `@memory` lookalike (for example `@memory.project`), or bare `session.*` in free
  prose (use `@memory.…` or move the reference into an `if:` condition)
- a tool writing a memory key not declared in any `memory.yml`
  (`undeclared_memory_write`)
- `else:` or `elif:` in prose, which is rejected; write one `if:` paragraph per case
- an ordered block whose id is a YAML key in the body rather than a fence attribute
  (`:::ordered_block id=pick_card`), or a tab-indented block body
- no `agent:` block in `agent.yml`, or a `persona` outside it
  (`config.agent.missing_section` / `config.agent.missing_persona`)
- an unquoted colon in an `agent.yml` `rules:` item (quote it or use a `>` folded
  scalar)

Unknown frontmatter keys are ignored rather than rejected, so a typo produces no
error and no effect. Check the spelling against the `skill.md` reference.

## When behavior is genuinely non-deterministic

If a symptom reproduces only sometimes: reproduce it 3-5 times in `rasa inspect`
before concluding, and capture the memory panel at the failing turn. If a control
lever exists for it, prefer the lever over prompt-wording experiments — levers are
framework-enforced on every run; prose changes shift probabilities.

## Beta caveats

If observed behavior contradicts this skill, trust the running system and check
the reference pages below. `rasa train` error messages are the most direct signal:
they name the offending file and key. Report a genuine discrepancy to the user
rather than silently working around it.

## Further reading

Full Maestro documentation: https://rasa-2f7eb63d.mintlify.site

Fetch `https://rasa-2f7eb63d.mintlify.site/llms.txt` for the page index, or
`https://rasa-2f7eb63d.mintlify.site/llms-full.txt` for every page in one file.
Read the specific page when this file is not enough; do not guess syntax.

Most relevant here:

- [Execution loop](https://rasa-2f7eb63d.mintlify.site/reference/execution-loop): the per-turn loop, and where conditions are evaluated
- [Constraint table](https://rasa-2f7eb63d.mintlify.site/reference/constraint-table): what the framework enforces versus the LLM at each level
- [System prompt](https://rasa-2f7eb63d.mintlify.site/reference/system-prompt): which sections the model sees, and what each agent.yml prompts key overrides
- [Prompt templates](https://rasa-2f7eb63d.mintlify.site/reference/prompt-templates): the assembled prompt and the framework tools offered per situation
- [Tools reference](https://rasa-2f7eb63d.mintlify.site/reference/tools): why a tool may not appear in the schema
