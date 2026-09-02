# Building risk-tiered step-up, one decision at a time

```text
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Time:          40–60 minutes
Prerequisites: a working Rasa Pro setup; you have built at least one skill before
```

This walks through *why* the pattern is shaped the way it is. The README says
what it does; this says which alternatives were tried and what is wrong with
them. Skip to chapter 5 if you only want the "what must a real OTP integration
not do" answer.

---

## Chapter 1 — the shape you probably have now

Almost every voice agent that authenticates does this:

```yaml
# skills/change_booking/skill.md
requires: session.project.authenticated
```

and somewhere upstream, a skill that sets that boolean. It is in this repository
too — `examples/mantle-voice-agent` does exactly this, and for a travel demo it
is a perfectly reasonable design.

Now write down the questions this shape cannot answer:

- The caller is authenticated. Authenticated *for what*?
- They verified at the top of the call to check a balance. They now want to
  reissue a card to a new address. What re-challenges them?
- You add `close_account` next sprint. What decided its risk?

Each of those is the same question: **the boolean records that verification
happened, not how much it was worth.** A single bit cannot carry a level, so
every downstream skill has to treat the weakest verification you accept as
sufficient for the strongest thing you offer.

The instinct is to add more bits — `verified_strongly`, `otp_passed`. That
works for two levels and collapses at four, because now every call site has to
know which combination its action needs, and they will disagree.

---

## Chapter 2 — put the level on the action, not the caller

The move is to stop storing a permission and start storing a *strength*, then
compare it against a requirement that belongs to the action.

Two pieces. First, an ordered lattice ([`authpolicy/tiers.py`](../authpolicy/tiers.py)):

```python
class AuthTier(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def satisfies(self, required: "AuthTier") -> bool:
        return self.rank >= required.rank
```

`str`-subclassing is not cosmetic: Rasa memory stores text, so a tier
round-trips through `session.project.auth_tier` without a conversion layer.

`satisfies` is `>=`, not `==`, and that is a deliberate usability decision. A
caller who stepped up to HIGH for a card reissue should not be re-challenged for
their balance thirty seconds later. Step-up strength is a high-water mark within
a session. Get this wrong in the `==` direction and you build something so
irritating that the team disables it, which is a worse security outcome than the
bug you were preventing.

Second, the requirement, keyed by action
([`authpolicy/actions.py`](../authpolicy/actions.py)):

```python
ActionPolicy(
    action="reissue_card",
    tier=AuthTier.HIGH,
    reason="Mails a payment instrument to an address supplied during this call.",
    irreversible=True,
)
```

Write the table before writing any tool. It is a risk conversation, and having
it in a table makes it a conversation you can have with someone who does not
read Python.

### The default that matters

```python
def tier_for(action: str) -> AuthTier:
    policy = POLICIES.get(action)
    return policy.tier if policy is not None else AuthTier.HIGH
```

Unknown actions require HIGH. This is the single most important line in the
module. The day someone adds `close_account` and forgets the table, the
alternative design waves it through and reports success. A registry that is
permissive by omission is not a registry.

`test_unknown_action_defaults_to_high` pins it.

---

## Chapter 3 — resolve it where the side effect is

Here is the decision most implementations get wrong, including one I wrote
first. Rasa offers a declarative place to require state:

```yaml
tool_constraints:
  - reissue_card:
      requires: session.project.verified_high
```

This is genuinely useful and this pattern uses the frontmatter layer. But
understand what it is: the orchestrator evaluates it against conversation state
to decide **which tools the model may select**. It shapes the model's options.

It does not run inside `reissue_card`.

The distinction is invisible while everything works and total when it does not:

- the YAML key is misspelled — constraints are config, and config typos are
  silent
- the skill is refactored and the constraint is not carried across
- the model is swapped for one that handles constraints differently
- the tool is called from another skill that never declared the constraint

In every case the routing control is absent and the function still runs. So the
binding decision goes on the line before the side effect
([`tools/banking.py`](../tools/banking.py)):

```python
try:
    require_tier("reissue_card", context)
except StepUpRequired as exc:
    return _step_up(exc, context)

return ToolResult(llm_response={"ok": True, "dispatched": True, ...})
```

Three things about this that are on purpose:

**It raises rather than returning falsy.** A return value can be ignored by a
caller who forgot to check it. An exception cannot.

**It is inline, not a decorator.** `@requires_tier("high")` would be tidier. It
would also put the check somewhere a reviewer skimming the diff of a *new* tool
would not notice its absence. The repetition is the point — six tools, six
visible guards, and a missing one is visible too.

**A missing context is unauthenticated.** `context is None` happens in unit
tests and tool-discovery probes. Neither is a reason to post a card.

### The refusal has to be a refusal

```python
return ToolResult(llm_response={"ok": False, "step_up_required": True, ...})
```

No dispatch reference, no address, no "your card is already on its way".
`test_refusal_carries_no_dispatch_data` asserts the absence of all four keys,
because the tempting failure is a helpful refusal that includes the address on
file "so the agent can confirm details while we verify" — which is a disclosure
to an unverified caller wearing a denial's clothes.

What it *does* carry is what the conversation needs to recover: which factor is
needed, and what to resume.

---

## Chapter 4 — the failure paths, and the downgrade bug

The interesting behaviour is on the way to *no*.

The bug this is shaped around: a caller fails the OTP for a card reissue, the
agent apologises, and then completes the reissue anyway — because the prose said
"if verification fails, offer to help another way" and the model read "help" as
"do the thing they asked for". The action succeeded on auth that was never
satisfied, and every log line says the call went fine.

Two independent mechanisms stop it:

**1. There is no code path from failure to a tier.**

```python
class Outcome(str, Enum):
    PASSED = "passed"
    RETRY = "retry"
    LOCKED_OUT = "locked_out"
```

`RETRY` and `LOCKED_OUT` both carry `granted=None`.
`test_a_failed_challenge_never_grants_a_tier` loops every outcome over every
budget position to assert it.

**2. The guard runs anyway.** Even if the conversation somehow reaches the tool
after a lockout, the tier in memory is NONE and the tool refuses.
`test_locked_out_caller_cannot_complete_the_high_action` asserts this one
directly, with no reference to the first mechanism.

Belt and braces, because the first is a policy decision expressed in prose and
data, and only the second is a fact about the process. Prose gets rewritten.

Lockout also calls `revoke`, dropping the caller to NONE — and note the ordering
in `_locked_out`: revoked *before* the result is returned, so there is no window
in which a locked-out caller still holds a tier.

### Ceilings

```python
def check_passphrase(spoken, attempts_used):
    return _evaluate(spoken, DEMO_PASSPHRASE, AuthTier.MEDIUM, attempts_used)
```

A passphrase grants MEDIUM. Not "MEDIUM unless the action needs more" — MEDIUM,
full stop. The function has no parameter that could make it grant HIGH. A
knowledge factor said out loud cannot bear the weight of an irreversible action,
and that limit is structural rather than a policy someone can override in a
config file.

### One voice-specific detail

```python
def _normalize(spoken: str) -> str:
    return " ".join(spoken.lower().replace(".", " ").replace(",", " ").split())
```

ASR output varies in casing, punctuation and spacing between runs of the *same
audio*. Comparing raw strings gives you a factor that fails for reasons the
caller cannot perceive or fix — and a support queue full of people who said the
right thing. The reflex fix is to widen the match until it accepts anything.

Normalise deliberately, and notice the trade: it makes the factor easier to say
correctly, and equally easier to say correctly *by someone who overheard it*.

---

## Chapter 5 — what a real integration must not do

The two seams are `verify_passphrase` and `verify_one_time_code` in
[`tools/verification.py`](../tools/verification.py). Both compare against a
hard-coded constant. Swap the comparison; nothing else moves, because the
lattice, the table and the guard never see a factor value.

When you swap it, here is what must not happen.

**Do not log the code.** Not at DEBUG, not "temporarily while we're
debugging", not in an exception's `repr`. Everything in this pattern goes
through `redact`, which returns a length and never the text — safe to leave on
in production, which is the property that matters, because a log line that must
be removed before release will not be.

**Do not put it in a `ToolResult`.** Tool results go to the model, into the
prompt, and into your LLM provider's logs. `send_one_time_code` deliberately
returns `"do NOT state the code yourself — you do not know it"` and does not
include the code, so the agent physically cannot read it out.

**Do not write it to memory.** Memory is serialised into the tracker and
survives the call. The pattern stores attempt *counts* and a tier — never a
factor.

**Think about the transcript.** This is the one that is specific to voice and
the one most often missed. The turn where the caller says their passphrase is a
plaintext credential in your conversation history. Your code never touched it —
ASR put it there. Redacting factor turns from the tracker is deployment work
this pattern cannot do for you, and it is why the README says a spoken
passphrase is not strong authentication.

**Do not compare with `==`.** Use a constant-time comparison
(`hmac.compare_digest`). The fixture here uses `==` because it guards nothing.

**Put the rate limit on the account, not the session.** The retry budget here is
per call, in session memory. Hang up, redial, fresh budget. Real lockout is
tracked against the account with backoff, and this pattern has nowhere to put it
because it has no account store.

---

## Chapter 6 — proving the guard, and why that is a chapter

```bash
make prove
```

It removes the four-line guard from `reissue_card`, runs the suite, asserts it
**fails**, restores the file in a `finally`, and asserts it passes again.

Why ship this? Because a negative test that has never been watched fail is
indistinguishable from one that asserts nothing, and the difference is invisible
in a green CI run. This repository has shipped that exact defect: a
"licence-clean" test whose assertions were vacuous, under which encumbered audio
passed every run for months.

When run against this pattern, removing the guard turns **7 tests** red,
including one reporting a dispatch reference returned to a caller holding
MEDIUM. That is what a load-bearing test looks like from the outside.

The script matches the guard block verbatim and **fails loudly if it cannot find
it**, rather than removing nothing and reporting a pass it did not earn. If you
reformat the guard, update the script — do not loosen the match.

Worth internalising as a habit beyond this pattern: after writing any test that
asserts something *cannot* happen, break the thing and watch it fail. It takes a
minute and it is the only way to know the test is connected to the code.

---

## Chapter 7 — the conversation around the guard

The guard makes the action impossible. It does not make the conversation good —
a caller told "no" with no path forward hangs up and calls the branch.

[`skills/step_up/skill.md`](../skills/step_up/skill.md) reads the refusal and
asks for the *named* factor:

```markdown
Call `check_auth_status` first. It tells you which action is pending, which tier
it requires, and which factor to ask for. Do not guess the factor — the same
caller needs different factors for different actions, and the tool knows which.
```

Two prose decisions worth copying:

**Explain why, once, without apologising.** "That one needs a code because it's
irreversible" is enough. Apologising for verification teaches callers that
verification is an imposition, which is the belief that makes social engineering
work.

**Say nothing on lockout.** `human_handoff` is explicit: do not say what was
wrong with the code, how many attempts were used, or what the right answer would
look like. Each of those is a bit of information to an attacker probing, and
none of them helps a legitimate caller who is already being handed to a person.

And in [`agent.yml`](../agent.yml), the rule that fights the downgrade at the
conversational layer:

```yaml
- >
  Never state or imply that a sensitive action completed unless the tool for it
  returned ok true. If a tool returns step_up_required, the action has NOT
  happened. Say what is still needed, and do not offer a workaround.
```

That rule is not the security control. The guard is. But an agent that refuses
correctly and then *describes* the refusal as a success has still misled the
caller, and the rule is what stops that.

---

## Where to go next

- Add an action. Put it in `POLICIES` first, then write the tool with the guard
  as its first statement. `test_every_high_tier_tool_refuses_medium` picks up
  any new HIGH action automatically — it reads the table, not a hand-maintained
  list.
- Run `make prove` after any change to the guard.
- Replace a factor with a real one, re-reading chapter 5 first.
- Read the README's "What this is NOT suitable for" before deploying anything
  descended from this. The pattern is a correct place to put an authorisation
  decision, demonstrated with factors not strong enough to carry it.
