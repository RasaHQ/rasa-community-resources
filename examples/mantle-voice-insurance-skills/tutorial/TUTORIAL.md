# Build with me: Voice insurance agent (Rasa Skills + Deepgram)

**Audience:** beginners and teams new to Rasa Skills  
**Length:** ~75–90 minutes  
**End state:** a speaking insurance agent (Poly) with full starter-pack parity

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
| `OPENAI_API_KEY` | LLM for routing + conversation (`gpt-5.2`) |
| `DEEPGRAM_API_KEY` | Speech-to-text **and** text-to-speech |

4. Gate the whole session on one command:

```bash
make verify
```

Do not move on until this prints **all checks passed**.

---

## Step 0 — Scaffold a voice Skills project (8 min)

**Teach:** Mantle projects are files, not flowcharts. Voice is configured once.
Session identity is loaded deterministically — not by the LLM.

Key files:

- [`agent.yml`](../agent.yml) — persona (Poly) + voice flags
- [`integrations.yml`](../integrations.yml) — OpenAI `gpt-5.2` + Deepgram (no temperature)
- [`endpoints.yml`](../endpoints.yml) — NLG rephraser model group (no temperature)
- [`skills/default_session_start/`](../skills/default_session_start/) — `execute_tool` then greet

Paste set: [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

```bash
make train
make inspect
```

**Verify:** Inspector opens and Poly greets Serena without you asking it to load a profile.

**Talking points:**

- Scaffold with `rasa init --engine mantle` (there is no `--template voice`)
- Zero-arg tools must not be left to the first LLM turn
- Deepgram Flux (ASR) + Aura (TTS) under `channels.inspector`

---

## Step 1 — First skill: FAQ in plain language (8 min)

**Teach:** A skill can be a single `skill.md` + optional `references/`.

Paste set: [`snippets/step-01-faq/`](snippets/step-01-faq/)

Try: “Does my homeowners policy cover flood damage?”

**Verify:** Answer comes from FAQ references, short enough to speak aloud.

---

## Step 2 — First tool: view policies (10 min)

**Teach:** Local-first tools. Shared tools live in `tools/`; a tool used by only
one skill should live in `skills/<name>/tools.py` (auto-discovered).

Paste set: [`snippets/step-02-view-policies/`](snippets/step-02-view-policies/)

Reference tools in **plain prose** (`Call list_policies`). There is **no**
`@tool.` token — `@` is only for `@skill.` / `@block.`.

Try: “What policies do I have?”

**Verify:** Agent lists Serena’s Car and Homeowner policies.

Demo customer: **Serena Williams** (id `123`)  
Run `make show-demo-data` for claim IDs and ready-made phrases.

---

## Step 3 — First hard guarantee: tool constraints (8 min)

**Teach:** Progressive control. Soft instructions become runtime guarantees.

The lookup tool is named `get_claim_status` (not `check_claim_status`) so it
does not collide with the skill id.

```yaml
tool_constraints:
  - get_claim_status:
      requires: session.check_claim_status.claim_number
```

Paste set: [`snippets/step-03-tool-constraints/`](snippets/step-03-tool-constraints/)

Try: “Check claim CLAIM1236”

**Verify:** Without a claim number, the model cannot call the lookup tool.

---

## Step 4 — File claim showcase (15 min)

**Teach:** Combine levers on one high-stakes skill:

1. `tool_constraints` + `requires_confirmation`
2. Scoped `if:` paragraphs (Car vs Homeowner)
3. Verbatim `utter:` + `responses.yml`
4. One `:::ordered_block` for strict collection order

Paste set: [`snippets/step-04-file-claim/`](snippets/step-04-file-claim/)

Local tools: `normalize_incident_date_value`, `submit_claim` in
`skills/file_claim/tools.py`. Shared `list_policies` via `import_tools`.

Try: “I need to file a claim on my car.”

**Verify:** Recording notice, auto-only fields, confirmation before submit,
claim number `12345`.

---

## Step 5 — Composition: status + inspection (12 min)

**Teach:** Small skills compose with `@skill.schedule_inspection`.

Paste set: [`snippets/step-05-composition/`](snippets/step-05-composition/)

Inspection tool is renamed `book_inspection` to avoid colliding with the skill.

Try: “What’s the status of CLAIM1236?” then agree to schedule an inspection.

---

## Step 6 — Remaining insurance skills (fast-forward) (8 min)

Paste set: [`snippets/step-06-remaining/`](snippets/step-06-remaining/)

Or reset to the finished tree:

```bash
git checkout HEAD -- skills tools lib
make train
```

**Verify:** “I want a human”, “Goodbye”, “What can you help with?”

---

## Step 7 — Voice pass with Deepgram (10 min)

Suggested spoken script:

1. “Hi Poly”
2. “What policies do I have?”
3. “Check claim CLAIM1234”
4. “I need to file a claim”
5. “Thanks, that’s all”

**Fallback:** If Zoom steals the mic, switch Inspector to text mode.

---

## Step 8 — Flywheel close (5 min)

1. Break a happy path (skip confirmation, change claim details mid-flow)
2. Add one tighter constraint or confirmation utterance
3. Retrain + re-inspect

---

## What you built

| Capability | Skill / tool |
|---|---|
| Session identity | `default_session_start` + `load_customer_profile` |
| Policy lookup | `view_policies` / `list_policies` |
| Claim status | `check_claim_status` / `get_claim_status` |
| Inspection | `schedule_inspection` / `book_inspection` |
| File a claim | `file_claim` / `submit_claim` |
| FAQ | `insurance_faq` |
| Handoff / goodbye | `human_handoff`, `goodbye`, `leave_feedback` |
| Voice | Deepgram ASR + TTS via Inspector |