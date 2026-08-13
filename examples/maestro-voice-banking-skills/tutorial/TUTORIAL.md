# Build with me: Voice banking agent (Rasa Skills + Deepgram)

**Audience:** beginners and teams new to Rasa Skills  
**Length:** ~75–90 minutes  
**End state:** a speaking retail banking agent (Rasano) with full banking parity

This guide is paste-first. Every step points at a complete file under
[`tutorial/snippets/`](snippets/). Prefer copying files over typing.

> The repo already contains the **finished agent**. If anything breaks during
> the live session, stay calm: run `make inspect` on the finished tree.

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
(including license expiry), the project structure, the demo bank, and live
connectivity to OpenAI and Deepgram — and names the exact fix for anything it
finds. Any time something misbehaves later, `make verify` is the first thing to
run.

---

## Step 0 — Scaffold a voice Skills project (8 min)

**Teach:** Maestro projects are files, not flowcharts. Voice is configured once.
A fresh project is scaffolded with `rasa init --engine maestro` (there is no
`--template voice`); we start from the finished tree here so we can focus on the
architecture.

Key files:

- [`agent.yml`](../agent.yml) — persona (Rasano) + voice flags
- [`integrations.yml`](../integrations.yml) — OpenAI (`gpt-5.2`, no `temperature`)
  + Inspector with Deepgram ASR/TTS
- [`.env`](../.env.example) — secrets

Paste set: [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

```bash
make train
make inspect
```

**Verify:** Inspector opens. Toggle the mic (or type) and say hello. Rasano should greet you.

**Talking point:** Inspector defaults to Deepgram for both listening and speaking when `DEEPGRAM_API_KEY` is set.

---

## Step 1 — First skill: FAQ in plain language (8 min)

**Teach:** A skill can be a single `skill.md` + optional `references/`.

Paste set: [`snippets/step-01-faq/`](snippets/step-01-faq/)

```bash
make train
make inspect
```

Try: “Are there fees to transfer money to friends?”

**Verify:** Answer comes from FAQ references, short enough to speak aloud.

---

## Step 2 — First tool: check balance (10 min)

**Teach:** Tools are Python functions with `@tool`. They are auto-discovered from
`tools/` (shared) or `skills/<name>/tools.py`.

Paste set: [`snippets/step-02-check-balance/`](snippets/step-02-check-balance/)

Try: “What’s my balance?”

**Verify:** Agent lists accounts, then reports a real balance from the demo DB.

Demo customer: **John Smith**  
Useful account: current `23456789`, savings `12345678`

Run `make show-demo-data` any time for the full list of accounts, cards, and
payees, plus ready-made phrases to try.

---

## Step 3 — First hard guarantee: tool constraints (8 min)

**Teach:** Progressive control. Soft instructions become runtime guarantees.

In `skills/check_balance/skill.md`, `check_balance` is invisible until
`session.check_balance.account_number` exists:

```yaml
tool_constraints:
  - check_balance:
      requires: session.check_balance.account_number
```

Paste set: [`snippets/step-03-tool-constraints/`](snippets/step-03-tool-constraints/)

**Verify:** Without an account number, the model cannot call the lookup tool
(it is removed from the schema).

---

## Step 4 — Card block showcase (15 min)

**Teach:** Combine levers on one high-stakes skill:

1. `tool_constraints` + `requires_confirmation`
2. Scoped `if:` paragraphs
3. Verbatim `utter:` + `responses.yml`
4. One `:::ordered_block` for strict card selection order

Paste set: [`snippets/step-04-block-card/`](snippets/step-04-block-card/)

Try (voice if possible): “My card was stolen.”

**Verify:** Recording notice plays, stolen warning appears, confirmation is
required before blocking, card ends as inactive.

---

## Step 5 — Composition: transfer + add payee (12 min)

**Teach:** Small skills compose with `@skill.add_payee`.

Paste set: [`snippets/step-05-transfer/`](snippets/step-05-transfer/)

Try: “Send 50 dollars to Robert from my current account.”

**Verify:** Confirmation gate before `process_transfer`. If the payee is missing,
the agent delegates to `add_payee` then resumes.

---

## Step 6 — Remaining banking skills (fast-forward) (8 min)

For live timing, copy the finished folders rather than rebuilding:

- `skills/list_payees`
- `skills/remove_payee`
- `skills/human_handoff`
- `skills/goodbye`
- `skills/intro`
- `skills/default_session_start`

**Teach — deterministic session start:** instead of asking the LLM to call a
no-argument tool on the first turn, the finished agent overrides the bundled
`default_session_start` skill. Its ordered block runs `execute_tool:
load_customer_profile` (no LLM schema involved) so the customer's identity is in
`session.project.*` before any skill activates, then greets. Fixed demo entities
should always be loaded this way, not left to a first-turn tool call.

Or reset to the finished tree:

```bash
git checkout tutorial/step-06 -- skills tools lib
make train
```

**Verify:** “Who can I pay?”, “Remove Food Market”, “I want a human”, “Goodbye”.

---

## Step 7 — Voice pass with Deepgram (10 min)

Keep Inspector open with the mic enabled.

Suggested spoken script:

1. “Hi Rasano”
2. “What’s the balance on my current account?”
3. “I lost my debit card”
4. “Thanks, that’s all”

**Talking points:**

- Deepgram Flux handles end-of-turn detection
- Aura TTS streams speech as the LLM responds
- Prefer short sentences in skill instructions for natural voice

**Fallback:** If Zoom steals the mic, switch Inspector to text mode and continue.

---

## Step 8 — Flywheel close (5 min)

1. Deliberately break a happy path (skip confirmation wording, change amount mid-transfer)
2. Add one tighter constraint or confirmation utterance
3. Retrain + re-inspect

**Teach:** Conversation-driven development beats guessing at instructions alone.

---

## What you built

| Capability | Skill |
|---|---|
| Greeting / orientation | `intro` + session greeting |
| Balance lookup | `check_balance` |
| Payees | `list_payees`, `add_payee`, `remove_payee` |
| Transfers | `transfer_money` (+ composition) |
| Card security | `block_card` |
| FAQ | `banking_faq` |
| Human handoff | `human_handoff` |
| Goodbye | `goodbye` |
| Voice | Deepgram ASR + TTS via Inspector |