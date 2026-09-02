# Handoff with context transfer

    Author:        Rod Rivera
    Assessed on:   2026-09-02
    Assessed by:   Rod Rivera
    Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
    Audience:      Practitioners whose agents hand callers to humans and whose callers then repeat themselves
    Time:          30–45 minutes

**A handoff is a state transfer, not a phone transfer.** The measure of a good
one is that the human starts from what the agent already knew, and the caller is
never asked a question they have already answered.

Every `human_handoff` skill in this repository today captures one free-text
`handoff_reason` string and opens a ticket. Identity, the tier it was verified
at, the structured intent, and everything already attempted are discarded at the
moment of handoff — so the caller repeats all of it to the human.

This pattern is what crosses the boundary instead, and the thing that stops the
wrong parts crossing with it.

## See the difference before reading any code

```bash
make compare      # no credentials, no model, no network
```

Two desk screens built from **the same session state**. On the left, what the
catalog transfers today. On the right, a context package.

```text
TODAY — one free-text handoff_reason
  CALLER      UNIDENTIFIED
  TRUST       tier=unverified — Identity NOT established.
  ASKING FOR  unknown (stage: stated)
  ALREADY TRIED: (nothing)

  The caller will now be asked 5 question(s) they already answered:
    ✗ Can I take your name?
    ✗ Can you confirm your date of birth?
    ✗ Which account is this about?
    ✗ What are you calling about today?
    ✗ Have you tried anything already?

THIS PATTERN — a structured context package
  CALLER      Jordan Rivera (cust_00417) via voice:+1-555-0100
  TRUST       tier=medium — Verified with a knowledge factor.
  ASKING FOR  Dispute a card transaction [card_last_four=4821, dispute_amount=$248.00, …]
  ALREADY TRIED:
    · send_otp_sms → failed (Carrier rejected the SMS twice. Do not resend to this number.)
    · raise_dispute → blocked (Dispute needs tier 'high'; caller is at 'medium'.)
  WITHHELD BY POLICY: auth_token, card_number, otp_code, pin_attempt, recording_url

  All 5 opening questions are answered. The desk asks none of them.
```

Five questions versus zero is not a matter of taste. It is
`handoffpkg.desk.unanswered_questions`, and it is asserted in the eval suite.

## What this teaches that nothing else in the catalog teaches

| Claim | Where it is made real |
|---|---|
| The transferred thing is **typed**, not a string | `handoffpkg/schema.py` — five sections |
| The human-readable summary **cannot disagree** with the fields | `summary` is a computed property, not a field |
| Redaction is part of the **contract**, not a cleanup pass | `handoffpkg/redaction.py` — an allowlist at the only choke point |
| A package **nothing consumes** is not a transfer | `handoffpkg/desk.py` reconstructs the caller from the package alone |
| "The caller is never asked twice" is a **number**, not a promise | `unanswered_questions()` → `()` |

## The package

```text
identity        customer_id, display_name, verified_tier, verified_factors, channel
intent          goal (identifier), goal_label, details{}, stage
attempts        [ {action, outcome, code, detail} ]  ← including the ones that FAILED
do_not_repeat   questions_answered, factors_verified, confirmed_facts
withheld_fields names of session fields deliberately not transferred
summary         DERIVED — see below
```

### The summary is derived, and here is the mechanism

This is the part most likely to be faked, so it is worth being precise about it.
`HandoffPackage.summary` is a **read-only property** that calls
`render_summary(self)` on **every access**:

```python
@property
def summary(self) -> str:
    return render_summary(self)
```

There is no `summary` field, no setter, no constructor argument, and no writer
anywhere in the package. A caller cannot store a summary that disagrees with the
structured fields **because there is nowhere to store one**. Change
`verified_tier` and the next read of `summary` says the new tier; there is no
second copy to forget to update.

`render_summary` is a pure function of the package — no I/O, no model call. That
matters more than prose quality: a summary written by an LLM at handoff time
would be a sixth piece of state, unversioned and free to contradict the other
five, and the human agent would read it because prose is faster to read than
fields.

The second half is `package_from_dict`, which **discards** any `summary` key it
is handed and recomputes from the fields. So a package that made a round trip
through a queue, a webhook, or someone's clipboard cannot smuggle in a summary
that contradicts its contents. Both halves are asserted:
`test_a_summary_smuggled_through_serialisation_is_discarded`.

### Verification tier — a declared dependency, not a competing scheme

`verified_tier` is `unverified | low | medium | high`. The `low/medium/high`
tiers are **owned by `patterns/voice-auth-stepup`**, which decides them from the
action being attempted. This pattern does not decide tiers and does not perform
step-up. It records the tier that was reached so the desk can see it, and
`handoffpkg/desk.py:permitted_actions` derives what the desk may do from it.

`unverified` is added here and is **not** a fourth auth tier: it is the value
before any check has happened. Keeping it distinct from `low` matters because
"we never checked them" and "we checked them weakly" must not read alike on an
agent desk. Unknown tiers fail closed (`tier_at_least` returns `False`).

**Verified against the sibling on 2026-09-02.** `voice-auth-stepup` landed
`authpolicy.tiers.AuthTier` with values `none / low / medium / high`, held in
project memory under the key `auth_tier`, and its `satisfies()` uses `>=` on a
rank lattice — the same ordering semantics as `tier_at_least`. The three real
tiers are identical. Two spellings differ, and both are **adapted here rather
than argued about**, because a pattern that only interoperates with a name it
chose itself does not interoperate:

| voice-auth-stepup | this pattern | how |
|---|---|---|
| `AuthTier.NONE` = `"none"` | `"unverified"` | `TIER_ALIASES` normalises it |
| memory key `auth_tier` | `verified_tier` | both are allowlisted; either is read |

When both spellings are present and **disagree**, `_resolve_tier` takes the
**weaker** of the two. Neither key tells you which is fresher, so preferring one
by position would be arbitrary — and the direction of the error is not
symmetric: under-stating strength costs the caller one step-up at the desk,
while over-stating it hands a human the authority to action an irreversible
change for someone never verified to that level.

`normalise_tier()` returns unknown values **unchanged** rather than coercing
them to a default, so they reach `tier_at_least` and fail closed there. Silently
rewriting an unrecognised tier into a valid one is how a desk ends up trusting a
tier nobody defined. Asserted by `test_the_siblings_tier_vocabulary_is_accepted`
and `test_an_unknown_tier_is_not_silently_rewritten`.

## The redaction contract

`SESSION_ALLOWLIST` in `handoffpkg/redaction.py` names every session key that
may cross. Everything else is dropped, and its **name** — never its value — is
recorded in `withheld_fields`.

An allowlist rather than a denylist, because the failure modes are not
symmetric. A denylist asks "is this one of the bad fields?" and is wrong the
first time someone adds a field nobody reviewed, which in a live agent is every
sprint. An allowlist asks "is this one of the fields we decided to send?" and its
failure mode is a *missing* field on the desk — which a human notices and
reports. Only one of the two leaks.

Deliberately absent, and the absences are the design:

| Not allowlisted | Why |
|---|---|
| `pin_attempt` | A spoken PIN. The caller's live credential. |
| `otp_code` | Still valid at the moment of handoff. |
| `card_number` | `card_last_four` is allowlisted instead — four digits identify a card to a human and cannot transact. |
| `passphrase_attempt` | A knowledge factor, in the clear. |
| `auth_token` | A bearer credential. |
| `ssn` | Not needed to serve the caller; needed to impersonate them. |
| `recording_url` | A separate surface with its own retention rules. |

The names still cross. That asymmetry is intentional: without the name, the desk
asks the caller to repeat a credential the system already holds; with the value,
the credential has been copied to a new surface.

### What the allowlist does NOT do

Stated plainly, because a privacy property that is claimed and not held is worse
than no claim at all.

1. **It governs session-state KEYS. It cannot police free text.** `handoff_reason`
   is allowlisted, so if a caller reads their card number aloud and it lands in
   that field, it crosses verbatim. This is demonstrated, not hedged:
   `test_freetext_in_an_allowlisted_field_is_transferred_verbatim` asserts the
   leak happens. `scan_freetext_risk()` *detects* the common shapes and is
   reported as advisory — **detection is not prevention**, and it will miss
   shapes it does not know.
2. **It is not a compliance control.** PCI, HIPAA and equivalents impose
   obligations on storage, transport and retention that a dataclass does not
   discharge. This shows where the boundary belongs; it does not certify one.
3. **It does not cover other surfaces.** The call recording, the ASR transcript,
   the desk agent's own notes, and any log written before the handoff are
   separate surfaces with separate boundaries. Each one has leaked in production
   somewhere.
4. **Allowlisting a container allowlists its contents.** Allowlist leaves, not
   dicts. `intent.details` is assembled from a fixed list of leaf keys for
   exactly this reason — asserted by
   `test_allowlisting_a_container_would_allowlist_its_contents`.
5. **The agent-side collection is a named list, not a sweep.** The handoff tool
   reads the keys in `_MEMORY_KEYS`, so a memory field added later is not
   collected until someone adds it there. That is a *completeness* gap — the
   desk silently misses a field — and never a *safety* gap, since an uncollected
   field cannot leak. Erring toward under-collection is the right direction to
   fail in, but it is a real gap and it is not glossed here.

   **This gap bit during development, and the story is the reason the test suite
   is shaped the way it is.** `_MEMORY_KEYS` originally omitted `account_id`, so
   `intent.details` was empty on every real handoff and the desk still asked
   "which account is this about?" — while the eval suite reported green, because
   it built its own session dict containing the key. Green tests, false claim;
   the same shape RULING-007 landed on. The fix was not just adding the key: it
   was `test_the_agent_path_retires_every_desk_question`, which parses the
   agent's *actual* `_MEMORY_KEYS` and the dispute skill's *actual*
   `memory.set` calls and drives the assertion from those, so the claim is
   tested against the path that runs rather than a convenient fixture.

   The credential keys `pin_attempt` and `otp_code` are in that list **on
   purpose**: they are collected and handed to the allowlist so the guard is
   genuinely exercised on the path the agent runs, asserted by
   `test_the_agent_collects_credentials_and_the_allowlist_stops_them`.

## The eval suite

```bash
make test     # 41 tests, no network, no credentials, no model
```

Two are required, and the second is load-bearing:

**(a) The package survives a handoff intact.** Built from session state,
serialised, delivered, read back, and compared field by field — then handed to
the desk, which reconstructs the caller from the package *alone*.

**(b) A sensitive field deliberately placed in session state does NOT reach the
package.** Seven credentials are planted in the demo session — including
`pin_attempt`, which is the real field name from
`examples/mantle-voice-agent/skills/authenticate/memory.yml`, not an invented
one. Every planted value is searched for in the serialised package, in the
derived summary, and in the rendered desk screen.

### Proving the guard fails

A guard nobody has watched go red is a docstring, not a guard. So it was removed
and the suite was run. Twice, because the first round found something.

**Round 1 — bypassing `filter_session`** (returning the whole session unfiltered,
withholding nothing):

```text
FAIL: test_a_field_nobody_anticipated_is_withheld_by_default
FAIL: test_every_key_the_agent_collects_is_either_allowlisted_or_withheld
FAIL: test_filter_session_returns_no_value_for_a_withheld_key
FAIL: test_summary_reflects_every_required_section
FAIL: test_the_agent_collects_credentials_and_the_allowlist_stops_them
FAIL: test_withheld_names_cross_but_values_do_not

Ran 41 tests
FAILED (failures=8)
```

Red — but note which tests did **not** fail: `test_no_sensitive_value_appears_
anywhere_in_the_package` still passed. That finding is worth more than the
demonstration was. The reason is that `build_package_from_session` reads specific
keys by name into typed dataclass fields, so bypassing the allowlist alone did
not put credential *values* into the package. A second, structural guard was
doing work nobody had credited to it.

**Round 2 — removing the structural guard as well**, letting `intent.details`
copy the session wholesale as a naive implementation would:

```text
FAIL: test_no_sensitive_value_appears_anywhere_in_the_package (field='pin_attempt')
FAIL: test_no_sensitive_value_appears_anywhere_in_the_package (field='otp_code')
FAIL: test_no_sensitive_value_appears_anywhere_in_the_package (field='card_number')
FAIL: test_no_sensitive_value_appears_in_the_derived_summary (field='pin_attempt')
FAIL: test_no_sensitive_value_reaches_the_rendered_desk_screen (field='pin_attempt')
FAIL: test_round_trip_through_the_boundary_loses_nothing
FAIL: test_allowlisting_a_container_would_allowlist_its_contents
... (13 distinct tests)

Ran 41 tests
FAILED (failures=31)
```

Every planted credential reached the package, the derived summary, and the
rendered desk screen. The guard was restored and the suite returned to `OK`
(41 tests).

**The lesson from round 1 is now in the code.** The boundary is two mechanisms,
not one: the allowlist decides *which keys* cross, and the typed schema decides
*which shapes* can hold a value at all. Testing only the first would have left
the second unverified, and the next person to refactor the schema would have had
no signal. Both are named in `handoffpkg/redaction.py`.

## Where a real contact-centre integration attaches

One function: `deliver()` in `handoffpkg/desk.py`. Replace it to write a Genesys
interaction, a Twilio Flex task attribute, or a Zendesk ticket field. Everything
else is unchanged.

**Nothing in this pattern models a real contact centre, on purpose.** Two rules
survive the swap:

1. What is handed over is a package produced by `build_package_from_session` —
   never raw session state, never a dict assembled at the call site.
2. Whatever the destination stores inherits this boundary. A CRM field that ends
   up holding a PIN is a leak no matter how careful the allowlist upstream was,
   and CRM fields are searchable, exportable, and retained for years.

## Files

| Piece | File |
|---|---|
| The typed package; derived `summary` | `handoffpkg/schema.py` |
| The derivation, as a pure function | `handoffpkg/summary.py` |
| The allowlist and the only session → package builder | `handoffpkg/redaction.py` |
| The fixture agent desk (receiving side) | `handoffpkg/desk.py` |
| The handoff skill and its tool | `skills/human_handoff/` |
| A flow that produces real state to hand off | `skills/dispute_transaction/` |
| The state a handoff carries | `memory.yml` |
| Eval suite | `tests/test_handoff_context.py` |
| Runnable desk / comparison | `scripts/agent_desk.py` |
| Guided walkthrough | [`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md) |

## Quick start

```bash
# Offline — no credentials needed
make compare
make desk
make test

# Talk to the agent
cp .env.example .env          # then fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
uv run rasa train
uv run rasa inspect
```

Say you want to dispute a charge, pick the Northgate Fuel one, and let the
dispute fail on tier. The agent hands you off — and
`python scripts/agent_desk.py fixtures/desk_queue/<id>.json` shows what the human
receives.

## Required secrets

- `RASA_LICENSE` — free Developer Edition key
- `OPENAI_API_KEY`

Names only; never commit values. See `.env.example`. Neither is needed for
`make test`, `make desk`, or `make compare`.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
