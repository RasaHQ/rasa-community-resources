# Build with me: Voice telecom care agent (Rasa Skills + Deepgram)

**Audience:** beginners and teams new to Rasa Skills  
**Length:** ~75–90 minutes  
**End state:** a speaking telecom care agent (Telano) with full starter-pack parity

This guide is paste-first. Every step points at a complete file under
[`tutorial/snippets/`](snippets/). Prefer copying files over typing.

> The repo already contains the **finished agent**. If anything breaks during
> the live session, stay calm: run `make inspect` on the finished tree,
> or recover with the tags documented in [`PRESENTER.md`](PRESENTER.md).

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
(including license expiry), the project structure, the demo telco DB, and live
connectivity to OpenAI and Deepgram — and names the exact fix for anything it
finds. Any time something misbehaves later, `make verify` is the first thing to
run.

---

## Step 0 — Scaffold a voice Skills project (8 min)

**Teach:** Mantle projects are files, not flowcharts. Voice is configured once.

Key files:

- [`agent.yml`](../agent.yml) — persona (Telano) + voice flags
- [`integrations.yml`](../integrations.yml) — OpenAI `gpt-5.2` + Inspector Deepgram ASR/TTS
- [`endpoints.yml`](../endpoints.yml) — platform NLG / model_groups (not classic actions)
- [`skills/default_session_start/`](../skills/default_session_start/) — load profile then `utter_greet`
- [`.env`](../.env.example) — secrets

Paste set: [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

```bash
make train
make inspect
```

**Verify:** Inspector opens. Toggle the mic (or type) and say hello. Telano should greet you.

**Talking point:** Inspector defaults to Deepgram for both listening and speaking when `DEEPGRAM_API_KEY` is set.

---

## Step 1 — First skill: FAQ in plain language (8 min)

**Teach:** A skill can be a single `skill.md` + optional `references/`.

Paste set: [`snippets/step-01-faq/`](snippets/step-01-faq/)

```bash
make train
make inspect
```

Try: “What is the difference between rebooting and resetting a router?”

**Verify:** Answer comes from FAQ references, short enough to speak aloud.

---

## Step 2 — First tool: check bill (10 min)

**Teach:** Tools are Python functions with `@tool`. Prefer skill-local
`skills/<name>/tools.py` (auto-discovered). Only shared tools live in `tools/`
and use `import_tools`. Reference tools in plain prose — there is no `@tool.` token.

Paste set: [`snippets/step-02-check-bill/`](snippets/step-02-check-bill/)

Try: “Can you explain my February bill?”

**Verify:** Agent asks for the month if needed, then reports a real amount from the demo DB.

Demo customer: **Serena Williams** (`customer_id` `123`)  
Useful bill: February 2026 is **$55.00** (Internet)

Run `make show-demo-data` any time for bills, routers, and ready-made phrases.

---

## Step 3 — First hard guarantee: tool constraints (8 min)

**Teach:** Progressive control. Soft instructions become runtime guarantees.

In `skills/check_bill/skill.md`, `get_bill_summary` is invisible until
`session.check_bill.bill_month` exists:

```yaml
tool_constraints:
  - get_bill_summary:
      requires: session.check_bill.bill_month
```

Paste set: [`snippets/step-03-tool-constraints/`](snippets/step-03-tool-constraints/)

**Verify:** Without a month, the model cannot call the lookup tool
(it is removed from the schema).

---

## Step 4 — Router reset showcase (15 min)

**Teach:** Combine levers on one high-stakes skill:

1. `tool_constraints` + `requires_confirmation`
2. Scoped `if:` paragraphs
3. Verbatim `utter:` + `responses.yml`
4. One `:::ordered_block` for strict router selection order

Paste set: [`snippets/step-04-reset-router/`](snippets/step-04-reset-router/)

Try (voice if possible): “Please factory-reset my router.”

**Verify:** Reset warning plays, confirmation is required before the remote
reset, Wi-Fi name becomes `TelecomOfRasa-Setup`. Tool name is
`factory_reset_router` (not the same as the skill id).

Demo router: `RTR-123-01` (RasaGate Fiber X1)

---

## Step 5 — Composition: internet troubleshooting (12 min)

**Teach:** Small skills compose with `@skill.run_diagnostics`,
`@skill.reboot_router`, and `@skill.reset_router`.

Paste set: [`snippets/step-05-internet/`](snippets/step-05-internet/)

Try: “My internet is slow.”

**Verify:** Diagnostics run, reboot guidance appears when speed is low, and a
factory reset is offered only after reboot fails to restore speed.

---

## Step 6 — Remaining telecom skills (fast-forward) (8 min)

For live timing, copy the finished folders rather than rebuilding:

- `skills/default_session_start`
- `skills/intro`
- `skills/check_bill` (if not already pasted)
- `skills/telco_faq`
- `skills/run_diagnostics`
- `skills/human_handoff`
- `skills/goodbye`

Or reset to the finished tree on `main` and keep presenting.

**Verify:** “Hi”, “What can you do?”, “I want a human”, “Goodbye”.

---

## Step 7 — Voice pass with Deepgram (10 min)

Keep Inspector open with the mic enabled.

Suggested spoken script:

1. “Hi Telano”
2. “Can you explain my February bill?”
3. “My internet is slow”
4. “Thanks, that’s all”

**Talking points:**

- Deepgram Flux handles end-of-turn detection
- Aura TTS streams speech as the LLM responds
- Prefer short sentences in skill instructions for natural voice

**Fallback:** If Zoom steals the mic, switch Inspector to text mode and continue.

---

## Step 8 — Flywheel close (5 min)

1. Deliberately break a happy path (skip confirmation wording, or ask for a
   factory reset without naming a device)
2. Add one tighter constraint or confirmation utterance
3. Retrain + re-inspect

**Teach:** Conversation-driven development beats guessing at instructions alone.

---

## What you built

| Capability | Skill |
|---|---|
| Session open / identity | `default_session_start` |
| Orientation | `intro` |
| Bill lookup | `check_bill` |
| Speed diagnostics | `run_diagnostics` |
| User reboot guidance | `reboot_router` |
| Remote factory reset | `reset_router` (`factory_reset_router` tool) |
| Slow-internet journey | `internet_troubleshooting` (+ composition) |
| FAQ | `telco_faq` |
| Human handoff | `human_handoff` |
| Goodbye / feedback | `goodbye` |
| Voice | Deepgram ASR + TTS via Inspector |
