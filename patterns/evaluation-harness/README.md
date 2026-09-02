# Evaluation harness

    Author:        Rod Rivera
    Assessed on:   2026-09-02
    Assessed by:   Rod Rivera
    Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
    Audience:      Practitioners who need to know whether a change to their agent made it better or worse
    Time:          45–60 minutes

Three different questions get asked about an agent, and they need three
different instruments:

1. **Did the agent do the right thing?** — assertion-based end-to-end tests.
2. **Did the agent understand the user?** — dialogue understanding tests.
3. **Was the free-text answer any good?** — LLM-as-a-judge scoring.

Most teams reach for the third because it feels closest to "quality", and get
back a number that drifts between runs and cannot be debugged. This pattern is
a runnable harness for all three, and an argument about when each one is the
right tool.

The agent in this directory is a **fixture**, not the point. It is a two-skill
retail-banking assistant with hard-coded data, deliberately boring, so that a
failing test always means the agent changed and never that the data moved. The
harness is the subject.

## The core distinction

An **assertion** reads the conversation tracker and answers a yes/no question
about what happened: did this flow start, does this slot hold this value, did
this action run. It is exact and repeatable. Run it a thousand times against an
unchanged agent and you get the same answer a thousand times.

A **judge assertion** sends the bot's text to a second LLM and compares a
returned *score* to a threshold. It can evaluate things no assertion can express
— "is this answer actually supported by our policy document?" — and it pays for
that with variance, latency, and money.

The rule this pattern argues for:

> Assert everything you can express as a fact about the tracker. Reach for the
> judge only for free text, where there is no fact to assert.

Teams that invert this end up with a slow, expensive, flaky suite that measures
their judge's mood as much as their agent's behaviour.

## What it covers

| Piece | File |
|---|---|
| Deterministic tracker assertions | `tests/e2e/check_balance.yml` |
| LLM-judge scoring (grounded + relevant) | `tests/e2e/faq_support.yml` |
| Judge model configuration | `conftest.yml` |
| Command-level understanding tests | `tests/dialogue_understanding/check_balance_du.yml` |
| Fixture agent under test | `agent.yml`, `skills/` |

## Quick start

```bash
cp .env.example .env          # then fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
uv run rasa train
```

Then run each instrument:

```bash
# 1. Deterministic assertions — no LLM judge, cheap, run these on every commit
uv run rasa test e2e tests/e2e/check_balance.yml

# 2. LLM-as-a-judge — costs money and varies between runs
uv run rasa test e2e tests/e2e/faq_support.yml

# 3. Dialogue understanding — behind a feature flag
RASA_PRO_BETA_DIALOGUE_UNDERSTANDING_TEST=true \
  uv run rasa test du tests/dialogue_understanding/

# Which flow paths did the suite actually exercise?
uv run rasa test e2e tests/e2e/ --coverage-report
```

`rasa test e2e` and `rasa test du` are subcommands of `rasa test`, whose
choices are `{core,nlu,e2e,du}` — verified from `rasa test --help` on
3.20.0.dev6.

## Instrument 1 — assertions

`tests/e2e/check_balance.yml`. Each step is a user message plus a list of
assertions checked against the tracker after that turn.

The assertion types the engine ships are enumerated in
`rasa/e2e_test/assertions.py:75-87`, and their accepted YAML shape is pinned by
`rasa/e2e_test/schema/assertions_schema.yml`:

| Assertion | What it checks |
|---|---|
| `flow_started` | a flow with this id started |
| `flow_completed` / `flow_cancelled` | a flow reached its end / was cancelled |
| `slot_was_set` / `slot_was_not_set` | a slot holds (or does not hold) a value |
| `action_executed` | a named action ran |
| `bot_uttered` / `bot_did_not_utter` | response name, buttons, or `text_matches` regex |
| `pattern_clarification_contains` | the clarification pattern offered these flows |
| `generative_response_is_relevant` / `..._is_grounded` | LLM judge (see below) |

Two habits worth copying from that file:

**Assert absence, not just presence.** The `small talk must not activate a task
skill` case asserts `slot_was_not_set`. An agent that starts a flow for every
utterance can pass a suite made only of positive tests.

**Match on the fact, not the phrasing.** `bot_uttered.text_matches` takes a
regular expression, so the savings-balance test pins `"9,140"` — the number the
tool returned — and lets the model word the sentence however it likes. Pinning
the whole sentence gives you a test that fails on every prompt tweak, which
trains the team to ignore failures.

By default assertions may match anywhere in the turn. Setting
`assertion_order_enabled: true` on a step forces them to match in sequence, by
slicing the event list after each match
(`rasa/e2e_test/e2e_test_runner.py:487-505`).

## Instrument 2 — dialogue understanding tests

`tests/dialogue_understanding/check_balance_du.yml`. These test the command
generator in isolation: for each user message, which commands did it emit?

The mechanism is what makes them useful. Each user step is annotated with its
expected commands, and the runner **replays the annotated commands** to advance
the conversation rather than using the ones the model just predicted
(`rasa/dialogue_understanding_test/test_case_simulation/test_case_tracker_simulator.py:36-43`).
Two consequences:

- Every step is scored from the same conversational state, so **one early
  mistake does not cascade** into failures at every later step
  (`rasa/dialogue_understanding_test/README.md:29-33`).
- You find out *why* an e2e test failed. An e2e failure says the conversation
  went wrong; a DU failure says the agent misread turn 2.

Results come back as per-command precision, recall and F1
(`rasa/dialogue_understanding_test/command_metrics.py:17-27`), computed over
true/false positives and negatives per command type. That is the report to read
after swapping the model behind your command generator.

**Command syntax is versioned.** The `StartFlow(x)` / `SetSlot(k, v)` form used
in this pattern is syntax version v1, which is the engine default
(`rasa/dialogue_understanding/commands/command_syntax_manager.py:48-51`). Under
v2 and v3 the same commands serialize as `start flow x` and `set slot k v`
(`start_flow_command.py:225-228`, `set_slot_command.py:184-187`). If you change
the syntax version, these files must be rewritten.

DU tests sit behind `RASA_PRO_BETA_DIALOGUE_UNDERSTANDING_TEST=true` and work
only for CALM-based assistants (`rasa/dialogue_understanding_test/README.md:19`).

## Instrument 3 — LLM as a judge

`tests/e2e/faq_support.yml`. Two metrics ship, and **they are not variations of
one idea** — they are computed by completely different machinery. Confusing them
is the most common way to get a meaningless eval.

### Groundedness — a ratio of statements

`generative_response_is_grounded` prompts the judge to split the answer into
atomic statements and mark each one supported or unsupported against a ground
truth (`rasa/e2e_test/llm_judge_prompts/groundedness_prompt_template.jinja2:7-12`).
The score is then plain arithmetic:

    score = supported_statements / total_statements

from `rasa/e2e_test/utils/generative_assertions.py:156-166`. No embeddings are
involved. This is the metric for "did the agent make something up?"

The denominator is worth pausing on: it is chosen by the judge, not by you. A
verbose answer split into eight statements and a terse one split into two do not
have comparable score granularity — with two statements the only possible scores
are 0, 0.5 and 1.0, so a threshold of `0.8` means "both statements must be
supported". Read your thresholds as fractions of a small integer, not as
percentages.

### Relevance — cosine similarity of invented questions

`generative_response_is_relevant` does something quite different. The judge is
shown **only the answer** and asked to invent 3 questions that answer would
address (`answer_relevance_prompt_template.jinja2:1-9`, with `num_variations`
set to 3 at `assertions.py:1595`). Those questions and the user's real
question are then embedded, and the score is the **mean cosine similarity**
between them (`generative_assertions.py:123-153`).

The consequence is the single most important thing to understand about this
metric:

> Relevance never sees your ground truth. A confidently wrong answer to exactly
> the right question scores **high**.

Relevance detects evasion and topic drift. It cannot detect fabrication. That is
why the card-replacement case in this pattern asserts both metrics on the same
turn — each covers the other's blind spot.

Because it embeds text, relevance needs an **embedding model** as well as a
judge model; groundedness does not. The default is OpenAI `text-embedding-3-small`
(`generative_assertions.py:28-31`).

### Configuring the judge

`conftest.yml` names a model group, validated against
`rasa/e2e_test/schema/e2e_config_schema.yml:18-46`. Omit the file and the judge
still runs, defaulting to `gpt-4.1-mini-2025-04-14`
(`rasa/e2e_test/constants.py:69`). Name it explicitly anyway: **the judge model
is an input to your scores**, so an unpinned default silently rewrites your
results when it moves.

### Why a judge assertion can find nothing to score

This trips people up and the error message is unhelpful. Judge assertions do not
look at every bot message. With no `utter_source:` given, they consider only
messages whose source metadata is one of

    EnterpriseSearchPolicy · ContextualResponseRephraser · IntentlessPolicy

(`rasa/e2e_test/utils/generative_assertions.py:34-38`). A plain templated
response is **invisible** to them. Responses become eligible when they are
generated (enterprise search, intentless) or passed through the rephraser, which
stamps its own class name; the rephraser only rewrites responses that explicitly
set `rephrase: true` (`rasa/core/nlg/contextual_response_rephraser.py:122-124`).
Otherwise the utter source is the action name
(`rasa/core/actions/action.py:935-941`), which you can target by naming it in
`utter_source:`.

If a judge assertion behaves as though it never ran, check this first.

## What this harness cannot tell you

An eval that oversells itself is worse than no eval, because it launders a guess
into a number. Concretely:

**Judge scores vary between identical runs.** The judge is an LLM at nonzero
temperature deciding how to split statements and what to call supported. The
same answer can score 0.75 and 1.0 on consecutive runs. A single run near your
threshold is noise, not a signal.

**The agent is non-deterministic too.** Both the command generator and the
response text can differ between runs given identical input. A flipped test may
mean nothing changed except sampling.

**Small samples say very little.** Six test cases cannot separate a real
regression from chance. The reflex of "we fixed it, the test passes now" after a
single green run is exactly the failure mode this harness should protect you
from, not create.

**Each run costs money and time.** Every judge assertion is at least one LLM
call, and relevance adds embedding calls. This is why the deterministic suite
belongs in CI on every commit and the judge suite belongs on a schedule or
before a release.

**Coverage is not correctness.** `--coverage-report` tells you which flow paths
your tests touched (`rasa/e2e_test/e2e_test_coverage_report.py:44-66`). A path
can be fully covered by tests that assert nothing meaningful about it.

**Ground truth drift is silent.** The `ground_truth:` strings in
`tests/e2e/faq_support.yml` are copied from `skills/faq_support/tools.py`.
Change the policy in one place and the judge will faithfully report the agent as
ungrounded against a stale source. Nothing warns you.

## Designing an A/B experiment with this harness

A frequent question is whether *control levers* — scoped skill instructions,
ordered blocks, explicit tool constraints — beat letting a capable model run
autonomously. This harness can answer that for your agent. The design:

1. **Fix everything except the lever.** Same model, same fixture data, same test
   cases. Two agent variants: one with scoped instructions and tool constraints
   (as in `skills/check_balance/skill.md`), one with an open persona and no
   constraints.
2. **Define task completion as an assertion, not a judgement.** For this fixture
   it is `action_executed: get_balance` with the correct
   `slot_was_set: selected_account_id`. Deterministic, so it does not inherit
   judge variance.
3. **Vary the user phrasings**, not the assertions. Many paraphrases of each
   intent, including ambiguous and off-topic ones.
4. **Run each variant repeatedly** and compare completion *rates* with a
   confidence interval. Non-determinism means a single pass per variant tells
   you nothing.
5. **Only then add judge metrics**, for answer quality among the conversations
   that completed.

A widely repeated figure from Rasa office hours puts the improvement at roughly
30% better task completion for the controlled variant over about 100 simulated
conversations. **That report is unpublished and is not reproduced here.** Treat
it as an unverified internal claim and a reason to run the experiment on your own
agent, not as a result you can cite. This pattern ships no benchmark numbers of
its own.

## A note on numbered lists in skill instructions

Both skills here give their procedure as a numbered list rather than a
paragraph. Per guidance from the Rasa team, numbering signals a **non-skippable
sequence** to the model, where prose describing the same steps reads as
suggestions it may reorder or drop. `skills/faq_support/skill.md` uses this to
insist the policy lookup happens *before* the answer — which is precisely the
behaviour the groundedness assertions then verify. It is a small lever, and it
is the kind of thing the A/B design above exists to measure rather than assume.

## Required secrets

- `RASA_LICENSE` — free Developer Edition key
- `OPENAI_API_KEY` — used by both the agent and the judge
- `RASA_PRO_BETA_DIALOGUE_UNDERSTANDING_TEST` — set to `true` for `rasa test du`

Names only; never commit values. See `.env.example`.

## What breaks

- **Stable rasa-pro pins have no Mantle engine.** This pattern pins
  `3.20.0.dev6` exactly. A stable release resolves and then fails at runtime.
- **Python floor is 3.11.** A lower `requires-python` fails at lock time with a
  resolver error that never mentions Python.
- **`llm:` must be a model group reference.** Inline `provider:`/`model:` under
  `llm:` is rejected — the integration config forbids extra keys and requires
  `model_group`.
- **Prompt-tuning keys go beside `agent:`, not inside it.** Nested keys parse
  without error and are silently discarded.
- **Judge thresholds are not portable.** They are tuned against a specific judge
  model, embedding model, and set of ground-truth strings. Changing any of the
  three invalidates them.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
