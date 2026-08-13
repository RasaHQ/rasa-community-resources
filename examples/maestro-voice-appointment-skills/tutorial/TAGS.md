# Checkpoints — what the tree looks like at every step

One entry per chapter of [`TUTORIAL.md`](TUTORIAL.md). Use these to answer the
two questions that come up in every live session: *"where should I be right
now?"* and *"what is supposed to be broken yet?"*

Each checkpoint is defined by a snippet folder under [`snippets/`](snippets/).
Every folder mirrors the finished agent, so you can paste it, diff against it,
or fast-forward through it without having walked the step.

**Recovering to any checkpoint** is the same one-liner, because the finished
agent is the working tree:

```bash
git checkout -- skills tools lib
make train
```

---

## step-00-scaffold

**Snippets:** [`snippets/step-00-scaffold/`](snippets/step-00-scaffold/)

| Snippet file | Destination |
|---|---|
| `agent.yml` | `agent.yml` |
| `integrations.yml` | `integrations.yml` |
| `memory.yml` | `memory.yml` |
| `responses.yml` | `responses.yml` |
| `intro.skill.md` | `skills/intro/skill.md` |

A project that talks and nothing more. The Schedora persona, the voice rules
that shape every later instruction, project-wide memory seeded with Jamie Chen,
a verbatim greeting, and Deepgram wired for both ASR and TTS through Inspector.

**Works:** Schedora opens with the greeting before you say anything — that is
Rasa's bundled `default_session_start`. “Hello” gets you the `intro` skill, which
says what it can do and asks what you need, out loud.

**Not yet:** no tools, no database, no clinic knowledge. It cannot answer a
single real question.

---

## step-01-faq

**Snippets:** [`snippets/step-01-faq/`](snippets/step-01-faq/) → `skills/clinic_faq/`

The first skill, and the cheapest one possible: a `skill.md` plus a
`references/clinic_faq.md` covering opening hours, booking, cancellations, what
to bring, fees, and data handling. No tools, no memory, no YAML plumbing.

**Works:** “What are your clinic hours?”, “What is your cancellation policy?”
Ask something outside the references and Schedora declines rather than guessing.

**Not yet:** nothing is patient-specific. The agent knows the clinic but not the
person calling it.

---

## step-02-list-contacts

**Snippets:** [`snippets/step-02-list-contacts/`](snippets/step-02-list-contacts/)

| Snippet file | Destination |
|---|---|
| `clinic.tools.py` | `tools/clinic.py` |
| `database.py` | `lib/database.py` |
| `tool_helpers.py` | `lib/tool_helpers.py` |
| `skill.md` | `skills/list_contacts/skill.md` |
| `default_session_start.skill.md` | `skills/default_session_start/skill.md` |

The first tool call, and the SQLite demo clinic behind it. `tools/clinic.py`
holds only the two genuinely shared tools — `load_customer_profile` and
`get_contacts` — and `list_contacts` declares `get_contacts` in `import_tools`.
The session-start override arrives with them, so Jamie Chen's profile is loaded
before the first turn instead of by whichever skill happens to run first.

**Works:** “Who are my contacts?” returns Joe and Mary, names first and handles
only on request. The greeting still plays first, now after a profile load.

**Not yet:** everything is read-only. No tool in play can change anything, and
no skill has a `tools.py` of its own.

---

## step-03-constraints

**Snippets:** [`snippets/step-03-constraints/`](snippets/step-03-constraints/) → `skills/remove_contact/`

The first destructive operation, and therefore the first hard guarantee — plus
the first **skill-local** tool. `skills/remove_contact/tools.py` defines
`delete_contact`, auto-discovered and deliberately absent from `import_tools`.
It is constrained on `session.remove_contact.contact_handle` and gated behind
`requires_confirmation` with verbatim wording in the skill's `responses.yml`.

**Works:** “Remove `@JoeMyers`” prompts “Are you sure you want to remove
@JoeMyers from your contacts?” word for word. Denial keeps the contact; approval
deletes it.

**Not yet:** nothing writes new records — the agent can delete but not create.

**Note:** if you actually removed Joe on stage, run `make reset-db` before the
next demo.

---

## step-04-book-appointment

**Snippets:** [`snippets/step-04-book-appointment/`](snippets/step-04-book-appointment/)

| Snippet file | Destination |
|---|---|
| `appointments.py` | `lib/appointments.py` |
| `skill.md` | `skills/book_appointment/skill.md` |
| `tools.py` | `skills/book_appointment/tools.py` |
| `memory.yml` | `skills/book_appointment/memory.yml` |
| `responses.yml` | `skills/book_appointment/responses.yml` |

The showcase. Every control lever on one skill: two `tool_constraints`
(`query_available_slots` and `confirm_appointment_booking`, both skill-local),
`requires_confirmation` before the diary is written, scoped `if:` paragraphs for
urgent, routine, and follow-up visits, an `utter:` privacy notice on activation,
and a `:::ordered_block` that forces fetch → select → confirm. Slots come from
`lib/appointments.py`, generated deterministically rather than stored.

**Works:** “Book an appointment with Dr Patel” runs the full journey and ends
with a booking reference. “I need an urgent appointment with Dr Patel” takes the
urgent path.

**Not yet:** the booking journey is a dead end. Ask to save the doctor as a
contact and nothing happens.

---

## step-05-composition-add-contact

**Snippets:** [`snippets/step-05-composition-add-contact/`](snippets/step-05-composition-add-contact/)

| Snippet file | Destination |
|---|---|
| `add_contact/` | `skills/add_contact/` — `skill.md`, `tools.py`, `memory.yml`, `responses.yml` |
| `skill.md`, `memory.yml`, `responses.yml` | `skills/book_appointment/` (updated) |

`add_contact` as a standalone skill, plus the three-line scoped paragraph in
`book_appointment` that hands off to it with `@skill.add_contact` and resumes
afterwards. This is the step that shows skills do not have to grow to cover a
longer journey. It is also the clearest example of the two tool tiers in one
folder: local `save_contact` for the write, shared `get_contacts` for the
read-back when the contact already exists.

**Works:** book an appointment, then “Add Dr Patel as a contact” — the handle is
read back letter by letter, saved, and the booking closes out. “Save Mary's
number under `@MaryLu`” also works on its own.

**Not yet:** no way to reach a person, and no way to end the call gracefully.

---

## step-06-remaining

**Snippets:** [`snippets/step-06-remaining/`](snippets/step-06-remaining/)

| Snippet folder | Destination |
|---|---|
| `human_handoff/` | `skills/human_handoff/` — including `tools.py` |
| `goodbye/` | `skills/goodbye/` |
| `intro/` | `skills/intro/` — catch-up copy, identical to step 0 |

The fast-forward. `human_handoff` raises a callback ticket behind a confirmation
gate and refuses to queue anyone describing an emergency; its
`create_handoff_ticket` is local, so the skill has no `import_tools` at all.
`goodbye` closes the call and repeats the appointment time if one was booked.
`intro` is included so this folder is a complete catch-up set for anyone who
joined late; if you did step 0, you already have it.

**Works:** “I need a human” and “Thanks, that's all”. This is the finished agent
— all eight patient-facing skills plus `default_session_start`, matching the
tree in the README.

**Verify the whole thing:**

```bash
make verify
make train
make inspect
```

---

## Optional: real git tags

This repo ships without tags, because the working tree is already the finished
agent and that is the fastest recovery path on stage. If you would rather have
per-step tags to check out during a rehearsal, build them on a scratch branch by
pasting one snippet folder at a time:

```bash
git switch -c rehearsal
# paste snippets/step-00-scaffold/, then:
git add -A && git commit -m "step 0" && git tag tutorial/step-00
# repeat for each snippet folder through step-06
```

Then recovery to any checkpoint becomes:

```bash
git checkout tutorial/step-04 -- skills tools lib
make train
```

Delete the branch afterwards; keep the tags.
