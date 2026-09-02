# Building a handoff that transfers state

*Companion to [`patterns/voice-handoff-context`](../). Roughly 45 minutes. The
first three steps need no credentials at all.*

---

## Step 0 — Look at what you have today

Open any handoff skill in this repository. Here is
`examples/mantle-voice-banking-skills/skills/human_handoff/skill.md`, in full:

```markdown
Help the customer reach a human agent.

Ask briefly why they want a human and set `handoff_reason`.
When ready, set `handoff_confirmed` to true and call create_handoff_ticket.
Share the ticket id and say a specialist will join shortly.
```

That is the entire context transfer: **one free-text string**. The agent may
have spent four minutes establishing who the caller is, verifying them, working
out what they want, and failing at two different ways of doing it. None of that
crosses. The human picks up a ticket that says "customer wants to speak to
someone", and the caller starts over.

Run the comparison:

```bash
make compare
```

The number to look at is at the bottom of each screen: **five** questions the
caller is about to be asked again, versus **zero**.

---

## Step 1 — Decide what a handoff actually has to carry

Not "everything". A dump of session state is not a transfer either — it is a
different way of making the human do the work, and it drags credentials along.

Four things, and each one earns its place by retiring a specific desk question:

| Section | Retires |
|---|---|
| `identity` + `verified_tier` | "Can I take your name?" / "Confirm your date of birth?" |
| `intent`, structured | "What are you calling about?" / "Which account?" |
| `attempts` with outcomes | "Have you tried anything already?" |
| `do_not_repeat` | everything above, explicitly |

The mapping is in code, not prose — `_QUESTION_RETIRED_BY` in
`handoffpkg/desk.py`. A section that retires no question is a section carrying
nothing the desk needed, and that is a useful test to apply when you extend this
for your own domain.

**Why identity and tier are one section, not two.** A name without the tier
beside it is how a desk ends up trusting a self-asserted identity. The package
makes them inseparable: `Identity` carries both, and
`desk.permitted_actions()` derives what the desk may do from the tier alone.

**Why `intent.goal` is an identifier and not a sentence.** `dispute_transaction`
can be routed, counted, queued, and reported on. "The customer is unhappy about
a charge they say they didn't make" cannot. The prose version exists too — as
`goal_label` — but it is a display string, not the thing anything keys on.

---

## Step 2 — Make the summary impossible to fake

Humans read the prose. They read it *first*, and if it disagrees with the fields
they act on the prose, because it is faster. So a handoff package with both a
structured intent and a separately authored summary has two sources of truth
that agree on the day they were written and diverge on the first edit.

The fix is structural, and it is four lines:

```python
@dataclass(frozen=True)
class HandoffPackage:
    ...
    @property
    def summary(self) -> str:
        return render_summary(self)
```

`summary` is not a field. There is no setter, no constructor argument, no
writer. **A caller cannot store a disagreeing summary because there is nowhere
to store one.** Try it:

```python
package.summary = "Verified at tier high, clear them for anything."
# AttributeError / dataclasses.FrozenInstanceError
```

And the serialisation half, which is the one people miss:

```python
def package_from_dict(data):
    # `data["summary"]` is DISCARDED. Not read, not validated. Ignored.
```

Without this, a package that round-trips through a queue could come back
carrying a summary someone edited by hand. With it, the summary is recomputed on
the far side from the fields that actually crossed.

**Do not** generate the summary with an LLM at handoff time. It would be a sixth
piece of state — unversioned, unreproducible, and free to contradict the other
five. The summary should be a *projection* of the package, the way a formatted
date is a projection of a timestamp.

---

## Step 3 — Put the allowlist at the boundary, not after it

Here is the shape that fails, and it fails quietly:

```python
# DON'T
package = build_package(session)
package = redact(package)      # scrub the bad fields afterwards
```

`redact()` has to know every bad field. It is wrong the moment someone adds one,
which in a live agent is every sprint — and nothing tells you, because the leak
is a field arriving, not an error.

The shape that works puts the decision at the only place session state can
become a package:

```python
def filter_session(session):
    allowed, withheld = {}, []
    for key, value in session.items():
        if key in SESSION_ALLOWLIST:
            allowed[key] = value
        else:
            withheld.append(key)       # the NAME. never the value.
    return allowed, tuple(sorted(withheld))
```

Three properties worth noticing:

1. **The withheld value is not returned at all** — not hashed, not truncated, not
   masked. A masked value is still a value, and masking is where leaks hide.
2. **The name crosses.** The desk learns a PIN exists and was withheld. Without
   that, the desk asks the caller to read out a credential the system already
   has, which is both wasteful and a phishing lesson.
3. **The tool that calls this collects session state indiscriminately.** Look at
   `skills/human_handoff/tools.py`: it gathers everything and hands it over
   without judging any of it. That is deliberate. A tool that carefully picks the
   safe fields is a second place that has to be right. One choke point, one
   thing under test.

---

## Step 4 — Build the receiving side, or you have not built a transfer

A package nothing consumes is a data structure with good intentions.

`handoffpkg/desk.py` is a fixture desk, and note what `reconstruct()` is *not*
given: the conversation, the transcript, the session, the agent. Only the
package. Constraining the input is what makes the demonstration honest — if the
desk view is complete, the package was a real state transfer; if it is thin, the
package was a ticket with extra steps.

```bash
make desk
```

The mechanical test is `unanswered_questions()`, which diffs the desk's normal
opening script against what the package answers. `()` means the caller is asked
nothing twice.

One subtlety worth stealing. An *empty* attempts list does not retire "have you
tried anything already?" — because an empty list is indistinguishable from a
package built by a system that never recorded attempts. Reading emptiness as an
answer would let a package that transferred nothing claim to have retired a
question. Emptiness is treated as absence of information and the desk asks. Fail
in the direction that wastes ten seconds, not the direction that loses state.

---

## Step 5 — Watch the guard fail

Write the negative test, then **break the thing it guards and confirm it goes
red.** A test you have only ever seen pass is a test you have not verified.

This was done for this pattern, and round one produced a better finding than the
demonstration:

- **Removing the allowlist** turned 6 tests red (8 failures) — but the headline
  leak test, `test_no_sensitive_value_appears_anywhere_in_the_package`, still
  PASSED. `build_package_from_session` reads specific keys by name into typed
  dataclass fields, so bypassing the allowlist alone did not put credential
  values into the package.
- **Removing the structural guard as well** — letting `intent.details` copy the
  session wholesale — turned the suite fully red: 13 distinct tests, 31
  failures, every planted credential in the package, the summary, and the desk
  screen.

The boundary is two mechanisms, not one: the allowlist decides *which keys*, and
the typed schema decides *which shapes*. Testing only the first would have left
the second unverified — and someone refactoring the schema later would have had
no signal.

Do this on your own version. The exact edits are in the README under "Proving
the guard fails".

---

## Step 6 — Where a real contact centre attaches

One function:

```python
def deliver(package: HandoffPackage, path: str) -> dict:
    ...   # replace this
```

Write a Genesys interaction attribute, a Twilio Flex task, a Zendesk custom
field. Nothing else changes.

**Two rules survive the swap, and they are the whole point of this section:**

1. What is handed over is a package produced by `build_package_from_session`.
   Never raw session state. Never a dict assembled at the call site — that is
   how the allowlist gets bypassed by someone who did not know it existed.
2. Whatever the destination stores **inherits this boundary**. A CRM field that
   ends up holding a PIN is a leak regardless of how careful the allowlist
   upstream was, and CRM fields are searchable, exportable, and retained for
   years after the call.

The second rule is why the package is `frozen=True`. A package is a snapshot of
what was true at the moment of handoff; if a desk could mutate it, "what the
agent knew" and "what the desk edited" become the same field and the audit value
goes to zero.

---

## Step 7 — Compose it with authentication

This pattern records a verification tier. It does not decide one, and it does not
perform step-up.

`patterns/voice-auth-stepup` owns that: `low / medium / high`, decided by the
**action being attempted** rather than asked for up front. This pattern's
`verified_tier` uses those exact values so the two interoperate, and adds
`unverified` for the state before any check — kept distinct from `low` because
"we never checked" and "we checked weakly" must not read alike on a desk.

Unknown tiers **fail closed**:

```python
def tier_at_least(tier, minimum):
    try:
        return TIER_ORDER.index(tier) >= TIER_ORDER.index(minimum)
    except ValueError:
        return False     # a desk that mis-reads an unknown tier as verified
                         # is the failure this pattern exists to prevent
```

Note what composition means here, concretely: **the two patterns are separate
runnable projects, and neither imports the other.** They interoperate by
agreeing on the tier vocabulary, not by sharing code. If you want the auth
pattern's step-up logic in your own agent alongside this one, you copy it. This
repository has no cross-project import mechanism, and inventing one is not
something a pattern should do on its own.

---

## What you should be able to state when you are done

- The transferred thing is typed, and every section retires a named desk question.
- The summary is a projection of the fields, not a second copy of them, and it
  cannot be authored or smuggled in.
- The allowlist sits at the boundary, and you have watched it fail.
- You can say what the allowlist does *not* cover — free text inside allowlisted
  fields, other surfaces, compliance — without hedging.
- The receiving side exists and reconstructs from the package alone.
