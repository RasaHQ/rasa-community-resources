# Build with me: Voice appointment-booking agent (Rasa Skills + Deepgram)

**Audience:** beginners and teams new to Rasa Skills
**Length:** ~60–75 minutes
**End state:** a speaking clinic scheduling agent (Schedora) that books appointments, manages contacts, answers clinic questions, and hands off to a human

This guide is paste-first. Every step points at complete files under
[`tutorial/snippets/`](snippets/). Prefer copying files over typing.

> The repo already contains the **finished agent**. If anything breaks during
> the live session, stay calm: the working tree is already correct, so
> `make train && make inspect` puts you back on stage.

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
(including license expiry), the project structure, the skill and memory
definitions, the tool imports, the seeded demo clinic, the slot generator, and
live connectivity to OpenAI and Deepgram — and names the exact fix for anything
it finds. Any time something misbehaves later, `make verify` is the first thing
to run.

5. Meet the demo patient:

```bash
make show-demo-data
```

Demo patient: **Jamie Chen**, with two saved contacts — **Joe (`@JoeMyers`)**
and **Mary (`@MaryLu`)**. Keep that output on a second screen; it also prints
ready-made phrases to try.

---

## Step 0 — Scaffold a voice Skills project (6 min)

**Teach:** Mantle projects are files, not flowcharts. Voice is configured once,
at the project level, and then shapes everything you write afterwards.

Key files:

- [`agent.yml`](../agent.yml) — persona (Schedora) + voice flags + spoken rules
- [`integrations.yml`](../integrations.yml) — `gpt-5.2` + Inspector with Deepgram ASR/TTS
- [`memory.yml`](../memory.yml) — project-wide memory (`session.project.*`)
- [`responses.yml`](../responses.yml) — verbatim greeting
- [`.env`](../.env.example) — secrets

Paste set: [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

`intro.skill.md` goes to `skills/intro/skill.md`; the other four files sit at the
project root.

```bash
make train
make inspect
```

**Try:** “Hello”

**Verify:** Inspector opens. Toggle the mic (or type) and say hello. Schedora
introduces itself as the Clinic of Rasa assistant and asks what you need.

**Talking point:** Inspector defaults to Deepgram for both listening and
speaking when `DEEPGRAM_API_KEY` is set — Flux for ASR, Aura for TTS. Note the
rules in `agent.yml`: one or two short sentences, one question at a time, dates
spoken in words. Those are voice design decisions, not style preferences.

**Also note:** Schedora speaks first, before you say anything. That is Rasa's
bundled `default_session_start` skill uttering your `utter_greet`. In step 2 you
will override it to do real work before the first turn.

---

## Step 1 — First skill: clinic FAQ in plain language (5 min)

**Teach:** A skill can be a single `skill.md` plus a `references/` folder. No
tools, no memory, no YAML plumbing.

Paste set: [`snippets/step-01-faq/`](snippets/step-01-faq/) → `skills/clinic_faq/`

```bash
make train
make inspect
```

**Try:** “What are your clinic hours?”

**Verify:** The answer comes from `references/clinic_faq.md` — Monday to Friday,
8 AM to 6 PM — and it is short enough to speak aloud. Follow up with “What is
your cancellation policy?” to show retrieval picking a different section.

**Talking point:** The skill instructs the model to refuse rather than guess. Ask
something the references do not cover and Schedora offers the clinic team instead
of inventing a policy.

---

## Step 2 — First tool: list contacts (8 min)

**Teach:** Tools are Python functions with `@tool`. `tools/` at the project root
holds the ones **more than one skill** needs, and a skill declares those in
`import_tools`. Everything else lives in `skills/<name>/tools.py` and is
auto-discovered — you will write your first of those in step 3.

Paste set: [`snippets/step-02-list-contacts/`](snippets/step-02-list-contacts/)

| Snippet file | Destination |
|---|---|
| `clinic.tools.py` | `tools/clinic.py` |
| `database.py` | `lib/database.py` |
| `tool_helpers.py` | `lib/tool_helpers.py` |
| `skill.md` | `skills/list_contacts/skill.md` |
| `default_session_start.skill.md` | `skills/default_session_start/skill.md` |

```bash
make train
make inspect
```

**Try:** “Who are my contacts?”

**Verify:** Schedora reads back **Joe** and **Mary** from the seeded SQLite
clinic — names only, because handles are awkward to listen to. Ask “What are
their handles?” and it will spell out `@JoeMyers` and `@MaryLu`.

**Talking point — naming.** The tool is `get_contacts`, not `list_contacts`,
because `list_contacts` is already the *skill*. Keep them distinct and an
instruction like “Call `get_contacts`” has exactly one meaning; Rasa's validator
warns when prose names a skill id without the `@skill.` prefix. Note also what
the skill body does **not** contain: no `@tool.` syntax. That reference form does
not exist in Mantle — you ask for a tool in plain prose, and `make verify` fails
the build if a `skill.md` still uses it.

**Talking point — session start.** `skills/default_session_start/skill.md`
overrides Rasa's bundled opener. It is `routing.engine_managed: true`, so the
router never picks it; the engine runs it before the patient's first word. Its
ordered block executes `load_customer_profile`, then utters the greeting. Jamie
Chen is in memory before anyone says hello, which is why no other skill in this
project opens with “first, look up the patient”.

---

## Step 3 — First hard guarantee: tool constraints (7 min)

**Teach:** Progressive control. A soft instruction becomes a runtime guarantee.

Paste set: [`snippets/step-03-constraints/`](snippets/step-03-constraints/) → `skills/remove_contact/`

All four files land in the same folder, including `tools.py` — this is the first
**skill-local** tool. `delete_contact` is used by exactly one skill, so it lives
with that skill and is auto-discovered. Do not add it to `import_tools`; that
list is only for the shared `tools/` folder, and listing a local tool there is a
validation error.

Deleting a contact cannot be undone, so `delete_contact` is invisible to the
model until a handle exists, and it still needs an explicit yes:

```yaml
tool_constraints:
  - delete_contact:
      requires: session.remove_contact.contact_handle
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_remove_contact
        utter_on_user_denial: utter_remove_contact_cancelled
      on_success: utter_contact_removed
```

Constraints work on both tiers — a gate keys off the real Python function name,
wherever the function lives.

```bash
make train
make inspect
```

**Try:** “Remove `@JoeMyers`”

**Verify:** Schedora asks “Are you sure you want to remove @JoeMyers from your
contacts?” using the exact wording from `responses.yml`. Say no — nothing is
deleted. Say yes — the contact is gone. Then run `make reset-db` to put Joe back.

**Talking point:** Without a handle in memory, the tool is **removed from the
schema the model sees**. This is not a prompt asking nicely; the model cannot
call what it cannot see. The confirmation utterance is verbatim, so legal or
clinical wording never drifts.

---

## Step 4 — Showcase: book an appointment (14 min)

**Teach:** Combine every lever on one high-stakes skill.

1. `tool_constraints` — search is gated on `visit_reason`, booking on `booking_confirmed`
2. `requires_confirmation` — the diary is never written without an explicit yes
3. Scoped `if:` paragraphs — urgent, routine, and follow-up visits read differently
4. `utter:` on activate — the privacy notice plays every single time
5. One `:::ordered_block` — fetch slots, then select, then confirm, in that order

Paste set: [`snippets/step-04-book-appointment/`](snippets/step-04-book-appointment/)

| Snippet file | Destination |
|---|---|
| `appointments.py` | `lib/appointments.py` |
| `skill.md` | `skills/book_appointment/skill.md` |
| `tools.py` | `skills/book_appointment/tools.py` |
| `memory.yml` | `skills/book_appointment/memory.yml` |
| `responses.yml` | `skills/book_appointment/responses.yml` |

Both tools are skill-local: `query_available_slots` reads the diary and
`confirm_appointment_booking` writes to it. The write is named for what it does
rather than for the skill, so `book_appointment` stays unambiguously the skill.

```bash
make train
make inspect
```

**Try (voice if possible):** “Book an appointment with Dr Patel”

**Verify:** The privacy notice plays first. Schedora asks what the visit is for
before it can search — `query_available_slots` does not exist until
`visit_reason` is set. It offers two or three times in spoken form (“Tuesday the
eleventh at nine thirty in the morning”), reads the choice back, asks for
confirmation, and only then writes the appointment and reads out the reference.

**Talking point:** Slots are generated in `lib/appointments.py`, not stored, so
the demo never runs out of availability and the same search always returns the
same slots — which matters when you are recording this. Say “I need an urgent
appointment with Dr Patel” to trigger the urgent notice and the shorter script.

---

## Step 5 — Composition: booking calls add contact (10 min)

**Teach:** Small skills compose. A skill can hand off to another with
`@skill.add_contact` and pick the journey back up when it returns.

Paste set: [`snippets/step-05-composition-add-contact/`](snippets/step-05-composition-add-contact/)

| Snippet file | Destination |
|---|---|
| `add_contact/` | `skills/add_contact/` — including its own `tools.py` |
| `skill.md`, `memory.yml`, `responses.yml` | `skills/book_appointment/` (updated) |

`add_contact` writes with its own local `save_contact`, and imports the shared
`get_contacts` only to read the list back when a contact already exists. That is
the split in one folder: local for what only this skill does, shared for what
three skills do.

```bash
make train
make inspect
```

**Try:** book an appointment, then “Add Dr Patel as a contact”

**Verify:** Schedora says it needs the doctor's handle, delegates to
`add_contact`, reads the handle back letter by letter before saving, confirms the
save in one sentence, and returns to close out the booking.

**Talking point:** `add_contact` is a standalone skill — “Save Mary's number
under `@MaryLu`” works on its own. Composition is orchestration, not
duplication, so neither skill grew a branch it did not need.

---

## Step 6 — Remaining skills (fast-forward) (5 min)

For live timing, copy the finished folders rather than rebuilding them.

Paste set: [`snippets/step-06-remaining/`](snippets/step-06-remaining/)

- `human_handoff/` — confirmation-gated callback ticket for the clinic team,
  raised by its own local `create_handoff_ticket` and no `import_tools` at all
- `goodbye/` — closes the call, and repeats the appointment time if one was booked
- `intro/` — a catch-up copy, identical to what you pasted in step 0

Or reset to the finished tree, which this repo already contains:

```bash
git checkout -- skills tools lib
make train
```

**Try:** “I need a human”, then “Thanks, that's all”

**Verify:** Schedora asks why, confirms before raising the ticket, and reads out
a ticket number. `goodbye` closes cleanly without pitching anything else.

At this point your tree should look like this:

```text
.
├── agent.yml
├── integrations.yml
├── endpoints.yml
├── memory.yml
├── responses.yml
│
├── skills/
│   ├── default_session_start/
│   ├── intro/
│   ├── book_appointment/     + tools.py
│   ├── list_contacts/
│   ├── add_contact/          + tools.py
│   ├── remove_contact/       + tools.py
│   ├── clinic_faq/
│   ├── human_handoff/        + tools.py
│   └── goodbye/
│
├── tools/
│   └── clinic.py             shared only: load_customer_profile, get_contacts
│
├── lib/
│   ├── database.py
│   ├── appointments.py
│   └── tool_helpers.py
│
└── data/
    └── source/
```

---

## Step 7 — Voice pass with Deepgram (8 min)

Keep Inspector open with the mic enabled and run the whole agent by voice.

Suggested spoken script:

1. “Hi Schedora”
2. “What are your clinic hours?”
3. “Book an appointment with Dr Patel”
4. “Add Dr Patel as a contact”
5. “Thanks, that's all”

**Talking points:**

- Deepgram Flux handles end-of-turn detection, tuned in `integrations.yml` with
  `eot_threshold` and `eot_timeout_ms`
- Aura streams speech as the LLM responds, so the agent starts talking before the
  full turn is generated
- Every design choice you made is audible: short sentences, spoken dates, two
  options instead of ten, handles spelled out letter by letter

**Fallback:** If Zoom or another app steals the mic, switch Inspector to text
mode and keep going. The conversation is identical.

---

## Step 8 — Flywheel close (4 min)

1. Deliberately break a happy path — change the doctor mid-booking, or answer
   “actually, no” at the confirmation gate
2. Watch where the agent drifts, then tighten exactly one thing: a constraint, a
   scoped `if:`, or an `utter:` with fixed wording
3. Retrain, re-inspect, and confirm the drift is gone

```bash
make show-demo-data
make train
make inspect
```

**Teach:** Conversation-driven development beats guessing at instructions. Fix
what you observed, at the weakest level of control that actually guarantees the
behaviour.

---

## What you built

| Capability | Skill |
|---|---|
| Profile loaded before the first word | `default_session_start` |
| Greeting / orientation | `intro` + verbatim greeting |
| Clinic questions | `clinic_faq` with references |
| Contacts | `list_contacts`, `add_contact`, `remove_contact` |
| Booking | `book_appointment` (constraints, ordered block, composition) |
| Human handoff | `human_handoff` |
| Goodbye | `goodbye` |
| Voice | Deepgram ASR + TTS via Inspector |

| Control you used | Where |
|---|---|
| Prose instructions | `clinic_faq` |
| Shared tools + `import_tools` | `list_contacts`, `add_contact`, `remove_contact` |
| Skill-local `tools.py` | `remove_contact`, `book_appointment`, `add_contact`, `human_handoff` |
| Engine-managed session start | `default_session_start` |
| `tool_constraints.requires` | `remove_contact`, `book_appointment` |
| `requires_confirmation` | `remove_contact`, `add_contact`, `book_appointment`, `human_handoff` |
| Scoped `if:` paragraphs | `book_appointment` |
| `utter:` verbatim responses | `book_appointment` privacy + urgent notices |
| `:::ordered_block` | `book_appointment` slot selection |
| Skill composition | `book_appointment` → `add_contact` |

Next: read [`TAGS.md`](TAGS.md) for the per-step checkpoints.
