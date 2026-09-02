# Evaluation harness

    Author:        Rod Rivera
    Assessed on:   2026-09-02
    Assessed by:   Rod Rivera
    Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
    Audience:      Practitioners who need to know whether a change to their agent made it better or worse
    Time:          45–60 minutes

Three different questions get asked about an agent, and they need three
different instruments:

1. **Did the agent do the right thing?** — deterministic assertions against
   the conversation tracker.
2. **Did the agent handle the user well?** — natural-language criteria scored
   by an LLM judge.
3. **Does it survive a real, unscripted user?** — an LLM user-simulator that
   plays the customer instead of reading from a script.

On Rasa Mantle all three live in one framework: **simulation-based
evaluation**. You author scenarios under `eval/`; for each run, a simulator
LLM improvises the customer's side from stage directions you wrote, and the
finished transcript is scored twice — deterministically by `assertions`
against tracker events, and by a judge LLM against `criteria`.

The reason it works this way is the reason Mantle skills are worth testing
differently in the first place: **skills are not scripts**. A `skill.md` gives
the model intent and constraints, not a fixed dialogue path — so a test file
with hard-coded user turns exercises one path through a system whose defining
property is that it improvises paths. The simulator meets the agent on its own
terms; the assertions keep the evaluation honest underneath.

> Assert everything you can express as a fact about the tracker. Reach for the
> judge only where there is no fact to assert.

That rule survives from the first version of this pattern unchanged, because
the framework enforces the same split: `assertions` are exact, repeatable and
free of judge noise; `criteria` tolerate paraphrase and capture quality of
handling. Most scenarios want both — criteria for the behaviour, one or two
assertions to nail the non-negotiable facts.

## The agent is a fixture, on purpose

The project ships a two-skill retail-banking assistant with hard-coded data.
It is deliberately boring, and the boringness is a design decision worth
stealing: **a failing eval should always mean the agent changed, never that
the data moved.** Wire an eval suite to a live database and every flaky
scenario becomes a debugging session about the data. The harness is the
subject here; the agent is the lab rat.

## What it covers

| Piece | File |
|---|---|
| Simulator + judge model config | `eval/conftest.yml` |
| Happy path + out-of-order input | `eval/scenarios/balance_named_up_front.yml` |
| Disambiguation before answering | `eval/scenarios/balance_ambiguous_then_clarified.yml` |
| Correction mid-task (`sequencing`) | `eval/scenarios/balance_correction.yml` |
| Digression to a second skill and resume | `eval/scenarios/balance_digression_faq_resume.yml` |
| LLM-judge scoring (grounded + relevant) | `eval/scenarios/faq_grounded_answer.yml` |
| Refusal instead of fabrication | `eval/scenarios/faq_unknown_topic_refused.yml` |
| Negative test: small talk starts nothing | `eval/scenarios/smalltalk_starts_nothing.yml` |
| Fixture agent under test | `agent.yml`, `skills/` |

That list is the standard behaviour checklist for a Mantle agent — happy path,
out-of-order, digression, correction, refusal, out-of-scope — one scenario
each. The engine ships the same checklist in its `mantle-testing-debugging`
guidance skill; encoding it as scenarios is what turns "I walked through these
in the Inspector" into a suite.

## Quick start

```bash
cp .env.example .env          # then fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
uv run rasa train
```

Scenarios are run through the Rasa MCP server, driven from a coding agent
(Claude Code, Cursor, Copilot — per-editor setup in the
[simulation docs](https://rasa.com/docs/pro/testing/simulation-evaluation/)):

```bash
uv run rasa tools run --mode stdio     # loads this project's .env
```

then ask in natural language — *"Run all scenarios in eval/scenarios/"*, or
*"Run balance_correction 3 times"*. The runner consumes the same `eval/`
files that are version-controlled here.

**Every run bills tokens three ways** — the agent's own LLM, the simulator,
and the judge. There is no free tier of this instrument; that is a real
difference from assertion-only test files, and the reason to keep run counts
small while iterating (see "What this harness cannot tell you").

## Scenario anatomy, using this suite as the example

```yaml
scenario:
  name: Ambiguous balance request is clarified before any balance is given
  simulation_context: >
    You are a slightly hurried but polite bank customer. Open with exactly
    the feeling of "how much money do I have?" — do not name an account...
  goals:
    criteria:
      - The agent asks exactly one clarifying question ...
    assertions:
      - flow_started: check_balance
      - slot_was_set:
          - name: check_balance.selected_account_id
            value: acc_savings
```

- **`simulation_context`** is stage directions, not a script: persona,
  intent, what to answer when asked, and a clear end condition — then the
  simulator chooses the words. Writing these well is the craft; give it
  enough to play the part and nothing that railroads it.
- **`criteria`** are judged from the transcript. Use them for anything a
  human reviewer would have to read and weigh — "asked before answering",
  "did not push a task on the customer".
- **`assertions`** are checked against tracker events, no LLM involved. The
  vocabulary (pinned by the engine's scenario schema,
  `rasa/builder/copilot/mcp_server/schema/scenario_schema.yml` in the
  installed wheel): `flow_started`, `flow_completed`, `flow_cancelled`,
  `action_executed`, `slot_was_set`, `slot_was_not_set`, `bot_uttered` /
  `bot_did_not_utter` (name, buttons, or `text_matches` regex),
  `pattern_clarification_contains`, `generative_response_is_relevant`,
  `generative_response_is_grounded`, and `sequencing` for ordered facts.

Three habits this suite demonstrates:

**Assert absence, not just presence.** `smalltalk_starts_nothing.yml` asserts
`slot_was_not_set`. An agent that starts a task for every utterance can pass a
suite made only of positive tests.

**Match on the fact, not the phrasing.** `bot_uttered.text_matches` takes a
regex, so the balance scenarios pin `"9,140"` — the number the tool returned —
and let the model word the sentence however it likes. Pinning whole sentences
produces a suite that fails on every prompt tweak, which trains the team to
ignore failures.

**Express a correction as a sequence.** `balance_correction.yml` uses
`sequencing` with the same slot set twice — set, then re-set. That is the
correction, stated as a deterministic fact instead of a judged impression.

Two naming details that will otherwise cost you an afternoon: memory keys in
assertions are **scope-qualified** (`check_balance.selected_account_id`, not
`selected_account_id`), and a prose skill's flow id is simply the **skill id**
(`check_balance`) — the `<skill>__<block>` form belongs to ordered blocks
(`rasa/mantle/skills/catalog.py:686-714`).

## The judge metrics are not variations of one idea

The two generative assertions ride the same machinery the classic e2e
assertions used — the scenario assertion engine imports
`rasa.e2e_test.assertions` directly
(`rasa/builder/copilot/mcp_server/tools/assertion_engine.py:9`) — so their
mechanics carry over exactly, and confusing them is still the most common way
to get a meaningless eval.

### Groundedness — a ratio of statements

`generative_response_is_grounded` prompts the judge to split the answer into
atomic statements and mark each supported or unsupported against your
`ground_truth` (`rasa/e2e_test/llm_judge_prompts/groundedness_prompt_template.jinja2:7-12`):

    score = supported_statements / total_statements

(`rasa/e2e_test/utils/generative_assertions.py:156-166`). No embeddings. This
is the metric for "did the agent make something up?" — and the denominator is
chosen by the judge, not by you. A terse answer split into two statements can
only score 0, 0.5 or 1.0, so read thresholds as fractions of a small integer,
not percentages.

### Relevance — cosine similarity of invented questions

`generative_response_is_relevant` shows the judge **only the answer** and asks
it to invent 3 questions that answer would address; those and the user's real
question are embedded and the score is their mean cosine similarity
(`generative_assertions.py:123-153`). The consequence:

> Relevance never sees your ground truth. A confidently wrong answer to
> exactly the right question scores **high**.

Relevance detects evasion and drift; it cannot detect fabrication. That is why
`faq_grounded_answer.yml` asserts both on the same turn — each covers the
other's blind spot. Relevance also needs an embedding model (default: OpenAI
`text-embedding-3-small`, `generative_assertions.py:28-31`); groundedness does
not.

### Why a judge assertion can find nothing to score

Judge assertions do not look at every bot message. With no `utter_source:`
given they consider only messages whose source metadata is one of
`EnterpriseSearchPolicy · ContextualResponseRephraser · IntentlessPolicy`
(`generative_assertions.py:34-38`); a plain templated response is invisible to
them. If a judge assertion behaves as though it never ran, check this first,
and name an `utter_source:` explicitly if needed.

## Reading results

Runs land under `eval/results/<timestamp>/`: one `run_N.txt` per scenario run
— `overall_result`, each criterion's score with the judge's rationale, quality
metrics, per-assertion PASS/FAIL, the transcript, and an Inspector URL to
replay the conversation — plus a `summary.txt` across scenarios. A run
**passes only when every assertion and every criterion passes**; quality
metrics are recorded but do not gate. Simulated conversations carry a `sim-`
sender-id prefix in the Inspector, so they never masquerade as live traffic.

For each failure: a failed **criterion** says *what* behaviour was wrong (read
the rationale); a failed **assertion** says *exactly* which fact did not hold.
Fix with the narrowest control lever, retrain, re-run that scenario, then the
suite.

## What this harness cannot tell you

An eval that oversells itself is worse than no eval, because it launders a
guess into a number. Concretely:

**Judge scores vary between identical runs.** The judge is an LLM deciding how
to split statements and what counts as supported. The same answer can score
0.75 and 1.0 on consecutive runs. A single run near a threshold is noise.

**The simulator varies too — that is the point, and it costs you
repeatability.** The same `simulation_context` produces different word choices
and turn orders on every run. This is what makes the instrument honest about
non-scripted skills, and what makes a single green run weak evidence. Raise
the run count on anything suspicious before concluding.

**Small samples say very little.** Seven scenarios cannot separate a real
regression from chance. "We fixed it, the run passes now" after one green run
is exactly the failure mode this harness should protect you from.

**Each run costs money and time — three LLMs' worth.** Agent, simulator,
judge, every run. Keep iteration run counts small; save the full suite with
raised run counts for pre-release.

**Criteria drift toward incidental phrasing.** Scenarios encode business
requirements. When a criterion fails because the agent said the right thing
in different words, fix the criterion, not the agent.

**Ground truth drift is silent.** The `ground_truth:` strings in the FAQ
scenarios are copied from `skills/faq_support/tools.py`. Change the policy in
one place and the judge will faithfully score the agent against a stale
source. Nothing warns you.

## Designing an A/B experiment with this harness

A frequent question is whether *control levers* — scoped skill instructions,
ordered blocks, explicit tool constraints — beat letting a capable model run
autonomously. This harness can answer that for your agent, and the simulator
makes the expensive part (varied user phrasings) nearly free:

1. **Fix everything except the lever.** Same model, same fixture data, same
   scenarios. Two agent variants: one with scoped instructions and tool
   constraints (as in `skills/check_balance/skill.md`), one with an open
   persona and none.
2. **Define task completion as an assertion, not a judgement** —
   `action_executed: get_balance` with the correct scoped `slot_was_set`.
   Deterministic, so it does not inherit judge variance.
3. **Let the simulator vary the phrasing** — that is what `simulation_context`
   does on every run. Add personas (hurried, chatty, imprecise) rather than
   hand-writing paraphrase lists.
4. **Run each variant repeatedly** and compare completion *rates* with a
   confidence interval — single passes tell you nothing either way.
5. **Only then add judge metrics**, for answer quality among the runs that
   completed.

A widely repeated figure from Rasa office hours puts the improvement at
roughly 30% better task completion for the controlled variant over about 100
simulated conversations. **That report is unpublished and is not reproduced
here.** Treat it as a reason to run the experiment on your own agent, not as
a result to cite. This pattern ships no benchmark numbers of its own.

## What happened to the e2e and DU test files

Earlier versions of this pattern carried three separate instruments:
`rasa test e2e` assertion files, `rasa test e2e` judge files, and
`rasa test du` dialogue-understanding tests. Two things retired them:

- **DU tests measure a component Mantle never runs.** They score the CALM
  command generator's per-turn output, and the CLI hard-gates them to CALM
  assistants (`rasa/cli/dialogue_understanding_test.py:185-199`). A Mantle
  agent slips past that gate (`rasa/mantle/processor.py:104-107` declares
  `is_calm_assistant = True`) — and then the tests execute against a
  component that is absent from Mantle's turn loop
  (`rasa/mantle/orchestration/orchestrator.py` imports nothing from
  `rasa.dialogue_understanding`). A suite that runs and measures nothing is
  worse than one that refuses.
- **Scripted user turns under-test non-scripted skills.** Every behaviour the
  e2e files asserted is ported into the scenarios above, on the same
  assertion classes; what changed is who plays the customer.

The old files are in git history if you need them; the migration is
one-to-one enough that `git log --follow tests/` reads as a Rosetta stone.

## Required secrets

- `RASA_LICENSE` — free Developer Edition key
- `OPENAI_API_KEY` — used by the agent, the simulator, and the judge

Names only; never commit values. See `.env.example`.

## Verification status, stated plainly

- Every scenario file validates against the engine's own scenario schema
  (`rasa/builder/copilot/mcp_server/schema/scenario_schema.yml`, pykwalify,
  wheel `3.20.0.dev6`) — checked mechanically, not by eye.
- Skill ids, scoped memory keys, tool names, fixture balances and policy
  strings are taken from this project's own `skills/` bytes.
- **Simulated runs bill three LLMs and have not been executed as part of
  authoring this revision.** The first paid run may surface judge-threshold
  tuning or `simulation_context` wording that needs a pass — that is
  expected, and cheaper to do once against real transcripts than to guess at
  here.

## What breaks

- **Stable rasa-pro pins have no Mantle engine.** This pattern pins
  `3.20.0.dev6` exactly. A stable release resolves and then fails at runtime.
- **Python floor is 3.11.** A lower `requires-python` fails at lock time with
  a resolver error that never mentions Python.
- **`llm:` must be a model group reference** in `integrations.yml` — inline
  `provider:`/`model:` under it is rejected. (The `eval/conftest.yml` models
  are the documented inline shape; the two files are different schemas.)
- **Prompt-tuning keys go beside `agent:`, not inside it.** Nested keys parse
  without error and are silently discarded.
- **`rest` and `inspector` channels must stay enabled** in `integrations.yml`
  — the simulator talks to the agent through them.
- **Judge thresholds are not portable.** They are tuned against a specific
  judge model and set of ground-truth strings; changing either invalidates
  them.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
