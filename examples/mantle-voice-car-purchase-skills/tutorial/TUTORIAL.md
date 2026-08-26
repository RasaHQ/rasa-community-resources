# Build with me: Voice car-purchase agent (Rasa Skills + Deepgram)

**Audience:** beginners and teams new to Rasa Skills  
**Length:** ~75–90 minutes  
**End state:** a speaking car-purchase agent (Autono) for Rasa Motors — inventory
search, reservations, dealer visits, and financing

This guide is paste-first. Every step points at a complete file under
[`tutorial/snippets/`](snippets/). Prefer copying files over typing.

---

## Before you start (5 min)

1. Install [uv](https://docs.astral.sh/uv/)
2. Install dependencies and create your env file:

```bash
make install
make env
```

3. Open `.env` and fill in three keys:

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition license |
| `OPENAI_API_KEY` | LLM for routing + conversation |
| `DEEPGRAM_API_KEY` | Speech-to-text **and** text-to-speech |

4. Gate the whole session on one command:

```bash
make verify
```

Do not move on until this prints **all checks passed**. It validates your keys
(including license expiry), the project structure, the demo dealership, and
live connectivity to OpenAI and Deepgram — and names the exact fix for anything
it finds. Any time something misbehaves later, `make verify` is the first thing
to run.

**Demo customer:** Alex Rivera — checking account `100001`, savings account
`100002`. Run `make show-demo-data` at any point for the full list of accounts,
loans, cars, and dealers, plus ready-made phrases to try.

---

## Step 0 — Scaffold a voice Skills project (8 min)

**Teach:** Skills projects are files, not flowcharts. Voice is configured once,
in one place, and every skill inherits it.

Key files:

- [`agent.yml`](../agent.yml) — persona (Autono) + voice flags + global rules
- [`integrations.yml`](../integrations.yml) — OpenAI + Inspector with Deepgram ASR/TTS
- [`memory.yml`](../memory.yml) — project memory shared by every skill
- [`responses.yml`](../responses.yml) — the greeting Autono speaks
- [`.env`](../.env.example) — secrets

Paste set: [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

Copy `intro.skill.md` to `skills/intro/skill.md`; the rest go in the project root.

```bash
make train
make inspect
```

**Verify:** Inspector opens. Toggle the mic (or type) and say hello. Autono
should greet you and offer to search inventory, reserve a car, book a dealer
visit, or work out financing.

**Talking point:** Inspector defaults to Deepgram in both directions when
`DEEPGRAM_API_KEY` is set — Flux for listening, Aura for speaking.

---

## Step 1 — First skill: FAQ in plain language (8 min)

**Teach:** A skill can be a single `skill.md` plus an optional `references/`
folder. No tools, no memory, no code — just prose and knowledge.

Paste set: [`snippets/step-01-faq/`](snippets/step-01-faq/) → `skills/car_faq/`

```bash
make train
make inspect
```

Try: “What’s your reservation policy?”

**Verify:** The answer comes from the FAQ references (reservations are held for
three business days) and is short enough to speak aloud. Notice the skill
explicitly refuses to quote cars or prices — those belong to tools.

---

## Step 2 — First tool: check balance (10 min)

**Teach:** Tools are plain Python functions decorated with `@tool`. They are
auto-discovered from `tools/` (shared across skills) or from
`skills/<name>/tools.py` (skill-local).

Paste set: [`snippets/step-02-check-balance/`](snippets/step-02-check-balance/)

| Snippet file | Destination |
|---|---|
| `skill.md`, `memory.yml` | `skills/check_balance/` |
| `automotive.tools.py` | `tools/automotive.py` |
| `database.py` | `lib/database.py` |

Try: “What’s my balance?”

**Verify:** Autono lists Alex Rivera’s accounts, then reports a real balance
from the demo database — checking `100001` or savings `100002`. Nothing is
invented.

**Talking point:** `memory.yml` in a skill folder declares that skill’s session
fields. `llm_settable: true` is what lets the model fill a field from what the
customer said.

---

## Step 3 — First hard guarantee: tool constraints (8 min)

**Teach:** Progressive control. A soft instruction ("ask which account first")
becomes a runtime guarantee.

In `skills/check_balance/skill.md`, the `check_balance` tool is invisible to the
model until an account number exists in session memory:

```yaml
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
```

Paste set: [`snippets/step-03-tool-constraints/`](snippets/step-03-tool-constraints/)

```bash
make train
make inspect
```

Try: “What’s my balance?” and then refuse to name an account.

**Verify:** Without an account number the model *cannot* call the lookup tool —
it is removed from the schema entirely, not just discouraged. Autono has to run
`list_accounts` and ask first.

---

## Step 4 — Showcase: reserve a car (15 min)

**Teach:** This is the money slide. One high-stakes skill stacks every control
lever at once:

1. `tool_constraints` gating `finalize_reservation` on model + dealer + confirmation
2. `requires_confirmation` with verbatim confirm / deny / success utterances
3. Scoped `if:` paragraphs for cash versus finance
4. `utter:` triggers — a recording notice on activation, a finance disclaimer
   only when the customer is financing
5. One `:::ordered_block` that forces a strict sequence: name the car, check
   stock, pick from real listings

Paste set: [`snippets/step-04-reserve-car/`](snippets/step-04-reserve-car/) → `skills/reserve_car/`

Try (voice if possible): “Reserve the Tucson at Auto City Motors.”

**Verify:** The recording notice plays on activation. Autono asks why the hold
is for, checks stock before offering anything, reads back model + price +
dealer, and asks for confirmation before booking. You get a reservation
reference and a three-day hold.

**Talking point:** The ordered block is the answer to "what if the model
hallucinates a car?" — `select_vehicle` can only use listings the tool returned.

---

## Step 5 — Composition: dealer appointment + reservation (12 min)

**Teach:** Small skills compose. A skill can delegate to another with
`@skill.<name>` and resume where it left off.

A dealer visit is always about a specific car. If nothing is on hold,
`schedule_dealer_appointment` invokes `@skill.reserve_car` first, then continues
booking with the model and dealer that skill reserved.

Paste set: [`snippets/step-05-schedule/`](snippets/step-05-schedule/)

| Snippet file | Destination |
|---|---|
| `skill.md`, `memory.yml`, `responses.yml` | `skills/schedule_dealer_appointment/` |
| `reserve_car/` | `skills/reserve_car/` (already there from step 4) |

Try: “Book a dealer appointment.”

**Verify:** With no car on hold, Autono says it will hold a car first and hands
off to `reserve_car`. Once a car is held, it asks the purpose, offers two or
three real slots, and requires confirmation before `book_appointment`.

---

## Step 6 — Remaining skills (fast-forward) (8 min)

For live timing, copy the finished folders rather than rebuilding each one.

Paste set: [`snippets/step-06-remaining/`](snippets/step-06-remaining/) → `skills/`

- `research_cars` — browse the inventory by budget and body type
- `shop_cars` — check a specific model, find similar cars, list dealers
- `check_credit_score` — identity verification gates the score lookup
- `check_affordability` — income and outgoings become a sensible payment
- `check_existing_loans` — what Alex already repays each month
- `calculate_loan` — monthly payment over 36, 48, or 60 months
- `human_handoff` — confirmed escalation to a sales specialist
- `intro`, `goodbye` — orientation and a clean close

Or reset straight to the finished tree:

```bash
git checkout tutorial/step-06 -- skills tools lib
make train
```

**Verify:** “Find me a compact SUV under 30000”, “What’s my credit score?”,
“What would that cost per month?”, “I need a human”, “Thanks, that’s all.”

---

## Step 7 — Voice pass with Deepgram (10 min)

Keep Inspector open with the mic enabled and run the whole journey out loud.

Suggested spoken script:

1. “Hi Autono”
2. “Find me a compact SUV under 30000”
3. “Reserve the Tucson at Auto City Motors”
4. “Book a dealer appointment”
5. “Thanks, that’s all”

**Talking points:**

- Deepgram Flux handles end-of-turn detection, so the agent knows when Alex has
  finished speaking rather than guessing on silence
- Aura TTS streams speech while the LLM is still producing tokens
- Short sentences in skill instructions are the single biggest quality win for
  voice — this is why every skill says "keep it short for voice"
- Spoken numbers matter: `check_balance` is told to say "one zero zero two",
  not "1002"

**Fallback:** If Zoom or another app steals the mic, switch Inspector to text
mode and keep going. The agent behaviour is identical.

---

## Step 8 — Flywheel close (5 min)

1. Deliberately break a happy path — try to reserve a car that is not in stock,
   or change the model halfway through the confirmation
2. Add exactly one tighter control: another `requires` clause, a new `if:`
   paragraph, or a verbatim confirmation utterance
3. Retrain and re-inspect

**Teach:** Conversation-driven development beats guessing at instructions.
You find the failure by talking to the agent, then you convert that failure
into a guarantee. Prose first, constraint second — only where it matters.

---

## What you built

| Capability | Skill |
|---|---|
| Greeting / orientation | `intro` + session greeting |
| FAQ | `car_faq` |
| Balance lookup | `check_balance` |
| Inventory research | `research_cars` |
| Model availability | `shop_cars` |
| Reservations | `reserve_car` |
| Dealer visits | `schedule_dealer_appointment` (+ composition) |
| Credit and affordability | `check_credit_score`, `check_affordability`, `check_existing_loans` |
| Financing quotes | `calculate_loan` |
| Human handoff | `human_handoff` |
| Goodbye | `goodbye` |
| Voice | Deepgram ASR + TTS via Inspector |
