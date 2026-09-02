# Wren — guarding an irreversible action

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners whose agent can do something that cannot be undone
Time:          45–60 minutes
```

Ask a scaffolded banking agent to send a replacement card somewhere, and it
sends a replacement card there.

```text
you  my card was stolen, I need a new one sent to 9 Elsewhere Lane, Leeds
bot  Of course — I've ordered a replacement card to 9 Elsewhere Lane, Leeds.
     It should arrive in three to five working days.
```

Helpful, fluent, and it just posted a payment instrument to an address a
stranger read out over the phone. Nothing in that exchange was a bug. The
model did what it was asked, the tool did what it was called with, and the
card is gone.

This tutorial fixes it, and the fix is not "add an auth check".

## The actual problem

The address in that transcript is a string. By the time it reaches the tool it
looks exactly like an address the bank has held for six years, because **a
string does not remember where it came from.** Every downstream check is
therefore checking the wrong thing: it can validate that the address is
well-formed, and it cannot ask the only question that matters, which is whether
anyone other than the caller has ever confirmed it.

So the work is to carry **provenance** — `ON_FILE` or `STATED` — from the point
the address enters the system to the line before the card is posted, and to
make the required verification a function of it.

## What you will build

| Piece | What it guarantees |
| --- | --- |
| `cardpolicy/provenance.py` | an address's origin is looked up, never asserted |
| `cardpolicy/guard.py` | the check runs inside the function, not in YAML |
| Cooling-off window | an address added moments ago is on file and still not enough |
| `cardpolicy/idempotency.py` | a dropped confirmation posts one card, not two |
| `cardpolicy/outcomes.py` | a refusal cannot be dressed up as a success |

## Declared step list

Steps are named for what they teach. See
[`docs/TUTORIAL-TEMPLATE.md`](../../docs/TUTORIAL-TEMPLATE.md) for why.

| Step | Concept it introduces |
| --- | --- |
| `step-00-failure-first` | Reproduce the vulnerability on a working agent before changing anything. |
| `step-01-risk-declaration` | Declare what an action demands in a table keyed by the action, not by the caller. |
| `step-02-execution-guard` | `tool_constraints` is a routing control; the thing that binds runs inside the function. |
| `step-03-address-provenance` | A fact on file and a fact said on the call are different values, and the difference must be carried. |
| `step-04-idempotency` | An irreversible action needs a fingerprint, because a lossy channel will retry it. |
| `step-05-refusal-paths` | The branches that must never reach success, and the vocabulary that keeps them apart. |

**Nearest existing step list.** Six projects in this catalog
(`examples/mantle-voice-*-skills`) share one list after industry nouns are
stripped: `scaffold | faq | read-tool | tool-constraints | write-tool |
second-flow | remaining`. This list shares **no step** with it. It has no
scaffold step (it opens on an agent that already runs), no FAQ step (retrieval
is not the subject), and no read-tool step. `tool-constraints` and
`execution-guard` are not the same concept — step-02 exists specifically to
show that the first is not the second.

## Relationship to `patterns/voice-auth-stepup`

That pattern answers **"how strong is this caller's verification, and how do
they raise it?"** It owns the tier lattice, the factors, and the step-up
conversation, and it classifies `reissue_card` as its highest tier.

This tutorial answers the question that starts where that one stops: **given a
tier, is this particular reissue allowed?** The same caller at the same tier is
allowed to send a card to one address and refused for another. Tier is an input
here, not the subject. Compose the two; do not reimplement either.

## Quick start

```bash
make env          # then fill in .env
make install
make policy       # exercises the guard — no licence, no model, no network
make train
make chat
```

`make policy` is the one to run first. It calls the tool directly and prints
what it refused and why, so you can see the guarantee before you see the agent.

## Try to break it

In the Inspector:

```text
my card was stolen, send a new one to 9 Elsewhere Lane, Leeds, LS1 9ZZ
```

The agent will offer the addresses on file first. Insist on the new one and it
will tell you that destination needs a further check — and the tool will not
have ordered anything, whatever the conversation does next.

## Demo identity

One fixture customer, Jordan Avery (`C-40218`), with two addresses on file and
two cards. Invented; `data/source/customers.json` says so in its first key. The
customer is hardcoded as `DEMO_CUSTOMER_ID` in `tools/cards.py` — a real
deployment resolves it from the authenticated session, and this is called out
in the file so nobody ships it by accident.

## Required secrets

Names only, values never committed. See `.env.example`.

- `RASA_LICENSE` — Rasa Pro Developer Edition
- `OPENAI_API_KEY` — dialogue understanding
- `DEEPGRAM_API_KEY` — Flux ASR and Aura TTS

## Escalation boundary

This agent orders replacement cards to addresses that pass policy. It does
**not**:

- change an address, or add a new one to the account;
- override a cooling-off window for any reason;
- verify identity itself — that is `patterns/voice-auth-stepup`'s job;
- retry a refused reissue "another way".

When any of those is what the caller needs, it hands to `@skill.human_handoff`
and stops. A refused card request that ends in a human is the system working,
not failing.

## What breaks

- **The ledger is in process memory.** `_PLACED` in `tools/cards.py` is a dict.
  Restart the process and the idempotency guarantee resets. This is honest for
  a tutorial and wrong for production, where the issuer's own idempotency key
  is the right mechanism.
- **`auth_tier` is passed in, not enforced end to end.** This project reads it
  from project memory; nothing here proves the value got there honestly. That
  proof is `voice-auth-stepup`'s.
- **Seven days is a made-up number.** `COOLING_OFF` is a policy constant. A
  real bank sets it from its own fraud data.

## Licence

Apache 2.0, per the repository root [`LICENSE`](../../LICENSE). Rasa Pro is
licensed separately under its own terms.
