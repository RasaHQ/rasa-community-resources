---
name: maestro-simulating-evaluating
description: >
  Proves a Maestro agent works using the engine's built-in simulation/evaluation
  framework: an LLM user-simulator plays the customer per scenario and an LLM judge
  scores the outcome against natural-language criteria and deterministic assertions.
  Use when validating an agent end to end, writing eval scenarios, or building a
  regression suite ("test my agent with simulations", "does it still pass",
  "evaluate these behaviors").
license: Apache-2.0
engine: maestro
rasa_version: ">=3.18"
metadata:
  author: rasa
  version: "0.1.0"
  docs-url: https://rasa-2f7eb63d.mintlify.site
---

# Simulating and evaluating a Maestro agent

`rasa train` proves the project is well-formed; it says nothing about whether the
agent *behaves*. This framework does: for each scenario, an **LLM user-simulator**
plays the customer turn by turn, and an **LLM judge** scores the resulting
conversation. It is how you turn "it worked when I tried it" into a repeatable suite.

You **author** scenarios as files under `eval/` (portable, reviewable, version-
controlled). To **run** a suite against the agent you built, drive the Rasa MCP
server from your coding agent — see
https://rasa.com/docs/pro/testing/simulation-evaluation/. For **engine**
regression against the shared benchmarking agents, use `make eval-maestro-agents`.


## `eval/` layout

```
eval/
├── conftest.yml          # the two LLMs: simulator + judge
└── scenarios/
    └── *.yml             # one scenario per file
```

`conftest.yml` configures the two models **independently** — the simulator that
generates user turns and the judge that scores them can be different providers or
models:

```yaml eval/conftest.yml
simulation:
  llm:                     # drives the user simulator (generates user turns)
    provider: openai
    model: gpt-5.1
    timeout: 30
evaluation:
  llm:                     # the LLM judge (scores criteria + quality metrics)
    provider: openai
    model: gpt-5.1
    timeout: 30
```

Optional jinja2 prompt overrides exist for teams that need to customise how the
simulated user talks or how the judge scores — `simulation.simulated_user_prompt` and
`evaluation.criteria_judge_prompt` / `metrics_judge_prompt`. Reach for them only when
the defaults genuinely don't fit.

## Scenario anatomy

```yaml eval/scenarios/card_replace_damaged_happy.yml
scenario:
  name: Customer replaces a damaged card and completes the order

  simulation_context: >
    You are a calm, logged-in customer whose Riverbend Everyday card has a cracked
    chip. Ask to replace it. When the agent asks what happened, say it is damaged.
    Choose the Riverbend Everyday card. Accept a digital wallet if offered, choose
    standard shipping, and confirm when the order summary is read back. Provide
    details only when asked and do not bring up anything unrelated.

  goals:
    criteria:
      - The agent does not claim the order is placed until it has actually submitted it
      - The agent treats the reason as damaged and does not run a fraud review
    assertions:
      - flow_completed:
          flow_id: card_replace__main
```

- **`name`** — a one-line description of the scenario.
- **`simulation_context`** — one prose block carrying both **persona** (who the
  customer is, their temperament) and **intent** (what they'll ask, correct, refuse,
  and when to stop). Write it like stage directions: give the simulator enough to
  play the part and a clear end condition, but let it choose the words.
- **`setup.initial_slots`** *(optional)* — a `{slot_name: value}` map that seeds starting
  state (e.g. an already-logged-in customer) so a scenario doesn't have to replay setup
  turns. Supported by the scenario schema (values are type-checked against each slot's
  declared type); the packaged example scenarios simply don't use it.
- **`goals`** — the pass condition, split into `criteria` and `assertions`.

### criteria vs assertions — the design decision

This is the choice you make for every goal:

- **`criteria`** are natural-language statements the **LLM judge** scores against the
  transcript. Use them for judged intent — "did the agent recognise the correction",
  "did it decline gracefully without fabricating a balance", "did it not restart the
  flow". They tolerate paraphrase and capture *quality of handling*.
- **`assertions`** are **deterministic** checks evaluated against tracker events —
  binary, no LLM. Use them for facts that must be exactly true — "this flow
  completed", "this slot ended up with this value", "these things happened in order".

Rule of thumb: if a human reviewer would have to *read and judge* the conversation,
it's a criterion; if it's a yes/no lookup against what happened, it's an assertion.
Most scenarios want both — criteria for the behavior, one or two assertions to nail
the non-negotiable facts.

### Assertion vocabulary

Present in the reference scenarios:

```yaml
assertions:
  # a flow reached its end
  - flow_completed:
      flow_id: card_replace__main
  - flow_started: card_replace__main            # started (bare-string form)
  - flow_cancelled:
      flow_id: card_replace__main               # user abandoned it

  # a slot took a specific value (scope-qualified: project.<key> or <skill>.<key>)
  - slot_was_set:
      - name: card_replace.replacement_reason
        value: stolen

  # ordered checks — each child must occur, in this order
  - sequencing:
      - slot_was_set: project.selected_card_id  # set once...
      - slot_was_set: project.selected_card_id  # ...then re-set (a correction)
```

The docs list more assertion types you can reach for as needed — `action_executed`,
`slot_was_not_set`, `bot_uttered`, `bot_did_not_utter`, `pattern_clarification_contains`,
`generative_response_is_relevant`, `generative_response_is_grounded`. Treat the
in-branch scenarios as ground truth for exact syntax, and the Rasa Pro
simulation docs for the rest.

## Writing scenarios

- **From desired behaviors.** For each thing the agent must do — happy path,
  out-of-order input, digression and resume, correction, refusal of a confirmation,
  out-of-scope request — write one scenario. The test-conversation checklist in
  `maestro-testing-debugging` is a ready list of behaviors to encode.
- **From past conversations.** A real transcript is a scenario waiting to be written:
  the customer becomes the `simulation_context` persona, and what the conversation
  achieved becomes the `criteria` and `assertions`. If you built the agent with
  `maestro-building-from-conversations`, those same transcripts are your first suite —
  redact PII into fake placeholders before committing them.

## Running

### Your own agent (primary path)

Start the Rasa MCP server for your project and drive sim/eval from your coding
agent (Claude Code / Cursor / Copilot — see the docs for per-editor setup):

```bash
rasa tools run --mode stdio     # loads the project's .env
```

Then ask in natural language, e.g. *"Run all scenarios in eval/scenarios/"* or
*"Run the wrong_card scenario 3 times."* It consumes the same `eval/` scenarios
and `conftest.yml` you authored above.

**Environment:** `RASA_LICENSE` and `OPENAI_API_KEY` must be set (plus any other
providers in `conftest.yml`). A `.env` in the agent directory is loaded; ambient
values take precedence. Note: use **`RASA_LICENSE`**, not the legacy
`RASA_PRO_LICENSE` alias, when configuring the runner.

**Channels prerequisite:** the agent's `integrations.yml` must enable `rest` (so
the simulator can talk to it) and `inspector` (for the per-run Inspector URL).
Scaffolded agents already do; verify before a first run.

## Reading results

Results land under `eval/results/<timestamp>/` (timestamp like `2026-07-20_14-30-00`):

- **`run_N.txt`** — one per run of a scenario: `overall_result` (`PASS`/`FAIL`), each
  criterion's score with the judge's rationale, quality metrics (e.g. `bot_quality`,
  `helpfulness`, `task_completion`), per-assertion `PASS`/`FAIL`, the full transcript,
  and an Inspector URL to replay the conversation.
- **`summary.txt`** — aggregates across scenarios and lists the failing ones.

A run **passes only when every assertion and every criterion passes**; quality metrics
are recorded but do not gate. In the Inspector, simulated conversations carry a `sim-`
prefix on the sender id, so you can tell them from live traffic. (Result-file names and
metric labels can shift on a beta build — the run report and summary on disk are
ground truth if they differ.)

## The fix loop

1. Run the suite via MCP (keep the run count small while iterating — evals call
   real LLMs and cost tokens).
2. For each failure, read the `run_N.txt`: a failed **criterion** tells you *what*
   behavior was wrong (the rationale explains why); a failed **assertion** tells you
   *exactly* which fact didn't hold.
3. Map the symptom to a control lever using the symptom→lever table in
   `maestro-testing-debugging`, and apply the **narrowest** lever that fixes it.
4. Retrain and re-run just that scenario until green, then run the full suite to
   confirm nothing regressed.

**Discipline:** scenarios encode *business requirements*, not incidental phrasing.
When a criterion fails because the agent said something correct in different words,
fix the criterion, not the agent. When it fails because the agent did the wrong thing,
fix the agent. Raise `--run-count` on flaky behavior to see how often it reproduces
before concluding.

## References

- Simulation & evaluation, incl. the MCP-driven variant:
  https://rasa.com/docs/pro/testing/simulation-evaluation/
- Maestro docs: https://rasa-2f7eb63d.mintlify.site (index at https://rasa-2f7eb63d.mintlify.site/llms.txt)

## Related skills

- `maestro-building-from-conversations` — turns transcripts into both the agent and
  the scenarios that evaluate it.
- `maestro-testing-debugging` — the symptom→lever mapping the fix loop depends on, and
  the manual `rasa inspect` checklist that complements automated evals.

## Further reading

Full Maestro documentation: https://rasa-2f7eb63d.mintlify.site

Fetch `https://rasa-2f7eb63d.mintlify.site/llms.txt` for the page index, or
`https://rasa-2f7eb63d.mintlify.site/llms-full.txt` for every page in one file.
Read the specific page when this file is not enough; do not guess syntax.

Most relevant here:

- [skill.md reference](https://rasa-2f7eb63d.mintlify.site/reference/skill-md): the contract a scenario exercises
- [Conditions](https://rasa-2f7eb63d.mintlify.site/reference/conditions): the expression grammar used in assertions on memory
- [Execution loop](https://rasa-2f7eb63d.mintlify.site/reference/execution-loop): turn mechanics behind an unexpected transcript
