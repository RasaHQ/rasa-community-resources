# Recovery checkpoints — Autono live build

Each chapter of [`TUTORIAL.md`](TUTORIAL.md) has a checkpoint: a known-good
state of the project you can jump to if the live build goes sideways.

The names below are **conceptual tags**. If the tags exist in your clone, use
`git checkout`. If they do not, every checkpoint can be reconstructed by
copying from [`snippets/`](snippets/) — the snippets *are* the checkpoints, and
they are copied verbatim from the finished agent in the parent directory.

```bash
# Preferred, if tags exist
git tag -l 'tutorial/*'
git checkout tutorial/step-04 -- skills tools lib && make train

# Always works
cp -R tutorial/snippets/step-04-reserve-car/. skills/reserve_car/ && make train
```

After any recovery: `make verify`, then `make train`, then `make inspect`.

---

## `tutorial/step-00` — Scaffold and voice

**Snippets:** [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

After this chapter the project should contain:

```
agent.yml            persona (Autono), voice enabled, global rules
integrations.yml     OpenAI LLM + Inspector with Deepgram ASR/TTS
memory.yml           project memory (username, segment, car_model, dealer_name…)
responses.yml        utter_greet
.env                 RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY filled in
skills/intro/skill.md
```

**Restore:**

```bash
cp tutorial/snippets/step-00-scaffold/agent.yml \
   tutorial/snippets/step-00-scaffold/integrations.yml \
   tutorial/snippets/step-00-scaffold/memory.yml \
   tutorial/snippets/step-00-scaffold/responses.yml .
mkdir -p skills/intro
cp tutorial/snippets/step-00-scaffold/intro.skill.md skills/intro/skill.md
```

**Green light:** `make train` succeeds and Autono greets you in Inspector.

---

## `tutorial/step-01` — FAQ skill

**Snippets:** [`snippets/step-01-faq/`](snippets/step-01-faq/)

Adds one skill with no tools and no memory:

```
skills/car_faq/skill.md
skills/car_faq/references/car_faq.md
```

**Restore:**

```bash
mkdir -p skills/car_faq
cp -R tutorial/snippets/step-01-faq/. skills/car_faq/
```

**Green light:** “What’s your reservation policy?” answers *three business days*
from the references.

---

## `tutorial/step-02` — First tool

**Snippets:** [`snippets/step-02-check-balance/`](snippets/step-02-check-balance/)

Adds the first Python-backed skill plus the shared tool and database layers:

```
skills/check_balance/skill.md
skills/check_balance/memory.yml
tools/automotive.py       (snippet: automotive.tools.py)
lib/database.py           (snippet: database.py)
```

**Restore:**

```bash
mkdir -p skills/check_balance tools lib
cp tutorial/snippets/step-02-check-balance/skill.md \
   tutorial/snippets/step-02-check-balance/memory.yml skills/check_balance/
cp tutorial/snippets/step-02-check-balance/automotive.tools.py tools/automotive.py
cp tutorial/snippets/step-02-check-balance/database.py lib/database.py
```

**Green light:** “What’s my balance?” lists Alex Rivera’s accounts and reports a
real balance for `100001` or `100002`.

---

## `tutorial/step-03` — Tool constraints

**Snippets:** [`snippets/step-03-tool-constraints/`](snippets/step-03-tool-constraints/)

Same two files as step 2, now with the guarantee in place:

```yaml
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
```

This is the constrained version and it matches the finished agent — step 2 and
step 3 differ only in that `tool_constraints` block, so recovering to step 3 is
always safe.

**Restore:**

```bash
cp -R tutorial/snippets/step-03-tool-constraints/. skills/check_balance/
```

**Green light:** refusing to name an account leaves the agent unable to look up
a balance; it must call `list_accounts` and ask.

---

## `tutorial/step-04` — Reserve car showcase

**Snippets:** [`snippets/step-04-reserve-car/`](snippets/step-04-reserve-car/)

The showcase skill, with every control lever in one file:

```
skills/reserve_car/skill.md        tool_constraints, requires_confirmation,
                                   if: paragraphs, utter: triggers, ordered_block
skills/reserve_car/memory.yml
skills/reserve_car/responses.yml   confirm / cancelled / reserved utterances
```

**Restore:**

```bash
mkdir -p skills/reserve_car
cp -R tutorial/snippets/step-04-reserve-car/. skills/reserve_car/
```

**Green light:** “Reserve the Tucson at Auto City Motors” plays the recording
notice, checks stock before offering anything, asks for confirmation, and
returns a reservation reference with a three-day hold.

---

## `tutorial/step-05` — Composition

**Snippets:** [`snippets/step-05-schedule/`](snippets/step-05-schedule/)

Adds the appointment skill, which delegates to `@skill.reserve_car` when no car
is on hold. The snippet folder bundles `reserve_car/` as well, because the
composition cannot work without it:

```
skills/schedule_dealer_appointment/skill.md
skills/schedule_dealer_appointment/memory.yml
skills/schedule_dealer_appointment/responses.yml
skills/reserve_car/                (from step 4)
```

**Restore:**

```bash
mkdir -p skills/schedule_dealer_appointment skills/reserve_car
cp tutorial/snippets/step-05-schedule/skill.md \
   tutorial/snippets/step-05-schedule/memory.yml \
   tutorial/snippets/step-05-schedule/responses.yml skills/schedule_dealer_appointment/
cp -R tutorial/snippets/step-05-schedule/reserve_car/. skills/reserve_car/
```

**Green light:** from a clean session (`make reset-db`), “Book a dealer
appointment” hands off to `reserve_car`, then resumes and books a slot behind a
confirmation gate.

---

## `tutorial/step-06` — Feature-complete agent

**Snippets:** [`snippets/step-06-remaining/`](snippets/step-06-remaining/)

Everything else, matching the finished tree:

```
skills/intro/                 skills/goodbye/
skills/research_cars/         skills/shop_cars/
skills/check_credit_score/    skills/check_affordability/
skills/check_existing_loans/  skills/calculate_loan/
skills/human_handoff/
```

**Restore:**

```bash
cp -R tutorial/snippets/step-06-remaining/. skills/
```

At this point the project equals the finished agent: 13 skills, the shared tool
module, the `lib/` helpers, and the demo dealership.

**Green light:** “Find me a compact SUV under 30000”, “What’s my credit score?”,
“What would that cost per month?”, “I need a human”, “Thanks, that’s all.”

---

## Steps 7 and 8 have no checkpoint

Step 7 (voice pass) and step 8 (flywheel) do not change the checked-in project
— they exercise it. If something breaks during either one, recover to
`tutorial/step-06` and carry on.

Step 8 asks the audience to add one new control on top of step 6. That edit is
intentionally throwaway; do not commit it, and reset with:

```bash
cp -R tutorial/snippets/step-06-remaining/. skills/
make train
```

---

## Quick reference

| Checkpoint | Snippet folder | Restores |
|---|---|---|
| `tutorial/step-00` | `step-00-scaffold/` | project root config + `intro` |
| `tutorial/step-01` | `step-01-faq/` | `car_faq` |
| `tutorial/step-02` | `step-02-check-balance/` | `check_balance`, `tools/`, `lib/` |
| `tutorial/step-03` | `step-03-tool-constraints/` | constrained `check_balance` |
| `tutorial/step-04` | `step-04-reserve-car/` | `reserve_car` |
| `tutorial/step-05` | `step-05-schedule/` | `schedule_dealer_appointment` + `reserve_car` |
| `tutorial/step-06` | `step-06-remaining/` | the remaining nine skills |
