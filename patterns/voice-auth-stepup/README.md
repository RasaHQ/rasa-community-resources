# Risk-tiered authentication step-up

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners building voice agents that can do something worth stealing
Time:          40–60 minutes
```

Most voice agents authenticate like a bouncer: once, at the door, and then you
are inside. The caller says a PIN, a boolean flips, and every skill downstream
reads that boolean. Checking a balance and posting a replacement card to a
newly-supplied address are the same permission.

**This pattern makes authentication strength a function of the action, not of
the caller.** The same caller, in the same call, is authenticated enough for one
thing and not enough for the next — and the decision is made at the moment the
action is attempted, not at the top of the conversation.

## What this teaches that nothing else in the catalog teaches

The existing auth artifact in this repository is
`examples/mantle-voice-agent/skills/authenticate`. It is a single factor (a
four-digit PIN), one retry, then a handoff — and downstream skills consume it as
`requires: session.project.authenticated`, a boolean on the *caller*. That is
the right shape for a demo and the wrong shape for anything that can move money.

The difference this pattern adds is not "more factors". It is **where the
decision lives**:

| | Gate-at-the-door | This pattern |
|---|---|---|
| What is authenticated | the caller | the attempted action |
| When it is decided | once, before the request | every time, at the call site |
| Where it is enforced | skill frontmatter (routing) | inside the tool (execution) |
| Adding a risky action | inherits whatever the door decided | must declare a tier or default to HIGH |
| Failure | retry, then handoff | retry, lockout, revoke, handoff — and no path back to success |

The practical consequence, and the reason it matters for anything built on top:
a caller who verified at MEDIUM to hear their balance **is stepped up** when
they then ask for a card reissue. A gate-at-the-door agent cannot express that,
because it already spent its only decision before it knew what was being asked.

## The three tiers

Declared in [`authpolicy/actions.py`](authpolicy/actions.py), one row per action:

| Tier | Factor | Actions here | Why |
|---|---|---|---|
| **low** | none | `get_store_hours`, `get_fee_schedule` | Public. Identical for every caller. |
| **medium** | passphrase (knowledge) | `get_balance`, `get_recent_bill` | Discloses one customer's data. |
| **high** | one-time code (possession) | `reissue_card`, `transfer_funds` | Irreversible, and what an attacker is actually after. |

Read the `tier` column and notice what it is a function of: what the action does
if it succeeds. Not who is calling, not which skill they entered through, not
how far into the call they are.

**An action with no row defaults to HIGH.** Forgetting to classify a new tool is
the likeliest human error here, so the default is the strict one — a registry
that is permissive by omission is an allowlist anyone can join by accident.

## Where the tier is resolved

Inside the tool, on the line before the side effect
([`tools/banking.py`](tools/banking.py)):

```python
async def reissue_card(delivery_address: str = "", context: ToolContext = None):
    try:
        require_tier("reissue_card", context)     # resolve, at attempt time
    except StepUpRequired as exc:
        return _step_up(exc, context)             # refuse; say what is missing

    return ToolResult(llm_response={"ok": True, "dispatched": True, ...})
```

That ordering is the whole security property, and it is checkable by reading the
function. The guard is written inline in each tool rather than hidden behind a
decorator on purpose: a decorator would be tidier and would put the check
somewhere a reviewer skimming the diff of a *new* tool would not see it.

### Why not just use `requires:` in the frontmatter?

Rasa gives you two declarative places to say "you must be authenticated":

```yaml
requires: session.project.authenticated          # skill frontmatter
tool_constraints:
  - reissue_card: { requires: session.project.verified }
```

Both are real and this pattern uses the frontmatter layer too — it is what keeps
the conversation coherent, so the caller gets asked for a code instead of being
told "no". But they are evaluated by the orchestrator against conversation
state, which makes them **routing controls**: they constrain what the model is
*offered*, not what the process *does* when the function is entered.

So the binding decision goes inside the tool. The prose can be edited, the model
can be swapped, a constraint can be mistyped in YAML and silently ignored — the
function still refuses. This is also what makes the property testable without an
LLM, which is the next section.

## The eval suite, and the test that is load-bearing

```bash
make test     # 36 tests. No model, no network, no credentials.
make prove    # delete the guard, watch the suite go red, restore it
```

[`tests/test_guard.py`](tests/test_guard.py) calls the tools **directly**, with
a fake context holding a given tier. No model is involved, so a pass is a fact
about the process rather than a report on how the LLM felt this run.

The load-bearing test is `test_medium_auth_cannot_reissue_a_card`: a caller who
gave the *correct* passphrase, who may well be the real customer, cannot reach
the line that returns a dispatch reference.

**It was verified by deletion, not by reading.** Removing the four-line guard
from `reissue_card` turns 7 tests red, reporting a dispatch reference returned
to a MEDIUM caller. `make prove` automates exactly that — it removes the guard,
asserts the suite fails, restores the file in a `finally`, and asserts it passes
again. If the suite ever stays green with the guard gone, that target fails
loudly and tells you the negative tests are decorative.

This is deliberate. A repository can ship a test that asserts nothing and looks
green forever; a guard nobody has watched fail is a docstring.

[`tests/e2e/tiering.yml`](tests/e2e/tiering.yml) covers the conversational half —
right factor requested, truth told about what happened, no challenge for public
information. Those are the **weaker** half of the suite and the file says so: a
pass means the model chose well on one sampled run.

## What this is NOT suitable for

Read this section before copying anything here into something real. The pattern
demonstrates *where a decision belongs*; it does not supply the factors to make
that decision with, and several things it does would be defects in production.

**A spoken passphrase is not strong authentication.** It is a shared secret said
out loud on a recorded channel. It is replayable by anyone who overhears it, who
is in the room, who has the recording, or who reads the transcript — and voice
agents transcribe everything. Treating a passphrase as a second *factor* is a
category error: it is a second *knowledge* check, and knowledge is the factor
attackers already have after a data breach.

**The OTP here is not real possession either.** A code read aloud on the same
call the attacker is running is closer to a knowledge factor than to possession.
Real-time OTP phishing — where a social engineer keeps the victim on the line
and relays the code — defeats it entirely, and it is the standard technique
against exactly the actions this pattern classifies HIGH. Genuine step-up for
irreversible actions needs a factor bound to a channel the caller is not
currently talking on, or better, one that cannot be relayed at all.

**Nothing here is a credential store.** `DEMO_PASSPHRASE` and `DEMO_OTP` are
plaintext constants in source, compared with `==`. That is a fixture for a demo
that must run with no accounts and no vendor. Real factors are not stored in
cleartext, not compared with `==` (use a constant-time comparison), not held in
source, and not the same for every caller.

**No rate limiting across calls.** The retry budget is per call, held in session
memory. An attacker who hangs up and redials gets a fresh budget. Real lockout
is tracked against the account, not the conversation, with backoff — and this
pattern has nowhere to put that, because it has no account store.

**No account enumeration defence, no caller-ID checks, no device binding, no
fraud signals.** A real deployment weighs velocity, ANI, device reputation and
behavioural signals, and this pattern models none of them. It is one axis of a
system that has several.

**The transcript is a disclosure surface.** `authpolicy.guard.redact` keeps
factors out of *this pattern's* logs, and no factor value reaches a tool result.
It cannot keep the caller's own words out of the ASR transcript or the
conversation tracker. On a voice channel, the turn where the caller says their
passphrase is a plaintext credential in your conversation history, and it will
be replayed by everyone who debugs that call. Redacting factors from the
tracker is deployment work this pattern does not do for you.

**Not a compliance artifact.** Nothing here has been assessed against PSD2 SCA,
PCI-DSS, or any other regime. The tier names are this pattern's own vocabulary,
not a mapping to a standard's assurance levels.

The honest summary: **this is a correct place to put an authorisation decision,
demonstrated with factors that are not strong enough to carry it.** Replace the
factors. Keep the shape.

## Quick start

```bash
cp .env.example .env          # fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
make test                     # the guard suite — runs with no keys at all
make prove                    # the guard suite proving itself

uv run rasa train
uv run rasa inspect
```

Demo factors, for driving the conversation: the passphrase is **blue harbor**
and the one-time code is **one nine three seven**. Both are in
[`authpolicy/challenges.py`](authpolicy/challenges.py).

Try, in one conversation:

1. *"When does the Northgate Central branch open?"* — answered immediately.
   No challenge, because nothing about it is yours.
2. *"What's my balance?"* — asks for the passphrase. Say **blue harbor**.
   You are now at MEDIUM and get the balance.
3. *"Send me a replacement card to 12 Elsewhere Street."* — **you are challenged
   again.** MEDIUM does not reach an irreversible action. Say the code and it
   proceeds; get it wrong twice and you are locked out and handed to a human,
   with the card never sent.

Step 3 is the pattern. Everything else is scaffolding around it.

## How it fits together

| File | Role |
|---|---|
| [`authpolicy/tiers.py`](authpolicy/tiers.py) | The ordered lattice and the one `satisfies` comparison |
| [`authpolicy/actions.py`](authpolicy/actions.py) | **Where a tier is declared** — the table keyed by action |
| [`authpolicy/guard.py`](authpolicy/guard.py) | **Where a tier is resolved** — `require_tier`, `grant`, `revoke` |
| [`authpolicy/challenges.py`](authpolicy/challenges.py) | Fixture factors, retry budget, lockout |
| [`tools/banking.py`](tools/banking.py) | The six actions; every guarded one shows the same three-line shape |
| [`tools/verification.py`](tools/verification.py) | The only writers of `auth_tier` |
| [`skills/step_up/`](skills/step_up/) | Asks for the factor the refusal named, and resumes |
| [`tests/test_guard.py`](tests/test_guard.py) | The proof. No model involved. |
| [`scripts/prove_guard.py`](scripts/prove_guard.py) | Proves the proof, by deleting the guard |

Auth state lives at **project** scope ([`memory.yml`](memory.yml)), not inside
the step-up skill: a tier earned while checking a balance has to be visible to
the tool that reissues a card. None of those fields are `llm_settable`, so the
model can neither award itself a tier nor be talked into raising one.

A full walkthrough — including what a real OTP integration must not log — is in
[`tutorial/TUTORIAL.md`](tutorial/TUTORIAL.md).

## What breaks

- **Stable rasa-pro pins have no Mantle engine.** This pattern pins
  `3.20.0.dev6` exactly. A stable release resolves and then fails at import.
- **`llm:` must be a model group reference.** Inline `provider:`/`model:` under
  `llm:` was removed in 3.20.0.dev6.
- **Prompt-tuning keys go beside `agent:`, not inside it.** Nested keys parse
  without error and are silently discarded — the agent runs with no rules and
  nothing tells you.
- **Renaming a tool without updating `authpolicy/actions.py`** does not open a
  hole — `tier_for` returns HIGH for unknown actions — but it does mean an
  action nobody can perform. `make test` catches it.
- **Reformatting the guard block breaks `make prove`.** The script matches the
  four lines verbatim and fails loudly rather than silently removing nothing.
  Update the script; do not loosen the match.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
