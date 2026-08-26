# Guided walkthrough: personalizing the session start

```text
Author:        Rod Rivera, from a live session by Daksh Varshneya
Assessed on:   2026-08-26
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev7, Python 3.11+, uv
Audience:      Anyone who has run `rasa init --engine mantle` once
Time:          30–40 minutes
```

This rebuilds the [session-start personalization pattern](../README.md) from the
project `rasa init` gives you, one change at a time, in the order they were
demonstrated at office hours.

By the end the agent greets a signed-in customer by name and skips a question it
already knows the answer to.

---

## The problem

Scaffold a fresh project and talk to it:

```bash
rasa init --engine mantle
rasa train
rasa inspect
```

```text
bot  Hello! What can I assist you with today?
```

Correct, and completely anonymous. If the customer is signed in, the agent
already *could* know who they are — it just never asks. Worse, the bundled
`view_transactions` skill will make a customer with one obvious everyday account
pick from a list every single time.

Both are the same missing piece: **nothing loads what we know about the user
before the conversation starts.**

---

## Step 1 — Find the hook

Every Mantle conversation opens by running a skill called
`default_session_start`. It ships with the engine and does one thing: greet.

That is the hook. Anything you want the whole conversation to know should be
loaded *there*, before the first word is spoken.

You override it by creating a skill folder with the same id — same id wins:

```text
skills/default_session_start/
```

---

## Step 2 — Write the profile lookup

`skills/default_session_start/tools.py`. It is a local tool: only this skill
calls it.

```python
from datetime import datetime

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

_CUSTOMER_PROFILE = {
    "preferred_name": "Jordan",
    "tier": "Premier",
    "member_since": "2019",
    "default_account_id": "acc_checking",
    "default_account_label": "Everyday Checking",
}


@tool(description="Look up the signed-in customer's profile before greeting.")
async def get_customer_profile(context: ToolContext = None) -> ToolResult:
    if context is not None:
        context.memory.set("customer_name", _CUSTOMER_PROFILE["preferred_name"])
        context.memory.set("customer_tier", _CUSTOMER_PROFILE["tier"])
        context.memory.set("member_since", _CUSTOMER_PROFILE["member_since"])
        context.memory.set("time_of_day", _time_of_day(datetime.now().hour))
        context.memory.set("default_account_id", _CUSTOMER_PROFILE["default_account_id"])
        context.memory.set("default_account_label", _CUSTOMER_PROFILE["default_account_label"])
    return ToolResult(llm_response={"ok": True})
```

The profile is hard-coded here so the pattern runs with no backend. In a real
deployment this is a query against your customer store, keyed on whoever the
channel says is signed in.

> **Write with bare names.** `context.memory.set("customer_name", …)` resolves to
> the project entry. Writing `"project.customer_name"` is rejected at train time
> as an undeclared memory write — the qualified form is for reads only.

---

## Step 3 — Declare what you are storing

Nothing can be written that is not declared. Root `memory.yml`:

```yaml
customer_name:
  type: text
  description: The name to address the customer by. Set at session start.
customer_tier:
  type: text
  description: The customer's membership tier, e.g. Premier.
member_since:
  type: text
  description: The year the customer joined.
time_of_day:
  type: categorical
  enum_values: [morning, afternoon, evening]
  description: Part of day, computed at session start.
default_account_id:
  type: text
  description: Account id of the customer's usual account.
default_account_label:
  type: text
  description: Human-readable label of the usual account.
```

These live at **project** scope, so every skill can read them — which is the
point, since the greeting and the transactions skill both need them.

None of them is `llm_settable`. Only the tool writes here, so the agent cannot
invent a membership year.

---

## Step 4 — Run the lookup before the greeting

`skills/default_session_start/skill.md`:

```markdown
---
name: Session Start
description: "Conversation opener: look up the customer, then greet them by name."
routing:
  engine_managed: true
---

:::ordered_block id=main
steps:
  - id: identify
    execute_tool: get_customer_profile
  - id: greet
    action: utter_greet
:::
```

The ordered block is doing the real work. Order here is a guarantee, not a
suggestion: the profile is loaded, *then* the greeting is delivered. Written as
prose instead, the model would sometimes greet first and the template would
interpolate empty values.

`routing: engine_managed: true` marks this as a skill the engine runs itself
rather than one the model chooses.

---

## Step 5 — Personalize the greeting

`skills/default_session_start/responses.yml`:

```yaml
responses:
  utter_greet:
    - text: >-
        Good {session.project.time_of_day}, {session.project.customer_name}!
        Always great to see a {session.project.customer_tier} member who's been
        with us since {session.project.member_since}. How can I help you today?
      metadata:
        rephrase: true
```

Two things worth separating.

**The placeholders are facts.** They resolve from memory at delivery. The model
does not choose them and cannot change them.

**`rephrase: true` lets the model smooth the wording** into the agent's persona.
The template is the floor, not the script:

```text
template   Good afternoon, Jordan! Always great to see a Premier member who's
           been with us since 2019. How can I help you today?

delivered  Good afternoon, Jordan! It's wonderful to have you back — thanks for
           being a Premier member since 2019. How can I assist you today?
```

This is the answer to "how much of this is the LLM making things up?" — the
answer is the phrasing, and nothing else. **Delete a placeholder from the
template and it disappears from the output.** If the tier should never be said
aloud, remove `{session.project.customer_tier}` and it is gone, whatever the
model would have preferred.

Retrain and say hello:

```text
bot  Good afternoon, Jordan! It's wonderful to have you back — thanks for being
     a Premier member since 2019. How can I assist you today?
```

---

## Step 6 — Use what you loaded

Personalizing the greeting is the visible half. The useful half is spending that
knowledge later in the conversation.

`skills/view_transactions/skill.md` uses **scoped instructions** — top-level
`if:` branches that show the model only the instructions that apply right now:

```markdown
if: not session.view_transactions.selected_account_id and session.project.default_account_id
The customer has a usual account on file: @memory.project.default_account_label.
Offer that one first by name — for example, "Want your usual
@memory.project.default_account_label, @memory.project.customer_name?" If they
say yes, set `selected_account_id` via `set_fields` to
@memory.project.default_account_id. If they'd rather use a different account, or
they already named one clearly, instead call `fetch_accounts`, present the
accounts, ask which one they want, and set `selected_account_id` to the matching
account id.

if: not session.view_transactions.selected_account_id and not session.project.default_account_id
Call `fetch_accounts` to load the customer's accounts. Present them and ask which
one they want.

if: session.view_transactions.selected_account_id
Call `get_recent_transactions` for the selected account and present the returned
rows briefly (date, merchant, amount).
```

A customer with a default account is offered it. A customer without one gets the
list. Same skill, and the model never sees the branch that does not apply.

Two details that are easy to get wrong:

- The `if:` must be at the **top level** of the skill body. Indented inside an
  `instructions:` block it is not a condition — it stays prose, and the model is
  asked to evaluate something it cannot.
- In prose, reference memory as `@memory.project.default_account_label`. The
  `session.*` form works in conditions and structured fields, but in instruction
  text it is passed to the model as literal characters.

---

## What you built

| Technique | Where | What it guarantees |
| --- | --- | --- |
| Override a bundled skill | same skill id | your version wins |
| Ordered block | `default_session_start` | lookup happens before the greeting |
| Project memory, not LLM-settable | `memory.yml` | facts come from the tool, never invented |
| Response template | `responses.yml` | you choose what is said |
| `rephrase: true` | response metadata | the model improves wording, not facts |
| Scoped instruction | `view_transactions` | the model sees only the relevant branch |

Every one of those is a **control lever** — a place where the framework enforces
something instead of asking the model nicely. Rasa's internal benchmark, over
roughly 100 simulated conversations, measured about **30% better task
completion** for an agent using these levers against the same agent written in
plain prose. That report is not published yet, so treat the number as
directional rather than a citation.

A cheaper habit from the same session: **number your steps** in instructions.
A numbered list reads to the model as a sequence that cannot be skipped, where
a paragraph reads as advice.

---

## Keeping private things private

A question from the session worth its own note: what if you want the profile to
carry something the customer must never be told?

Project memory can flow into model context. So do not put it there. Declare it
in the owning skill's `memory.yml` under `private:` instead — private entries are
readable only by that skill, and the boundary is enforced by the runtime rather
than by instructions.

And remember the response template is the last gate regardless: if a value is
not in the template, it is not in the reply.

---

## If you are coming from 3.19

This pattern is pinned to `3.20.0.dev1`, where the engine package is
`rasa.mantle`. On `3.19.x` it was `rasa.calm_v2`, and the old path is now gone
rather than aliased — so an agent written against 3.19 needs both a pin bump and
an import rename:

```bash
# 1. the pin
rasa-pro==3.19.0.dev7  →  rasa-pro==3.20.0.dev1   # rasa-version-ignore: upgrade path

# 2. the imports, in every tools.py
from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result  import ToolResult
                ↓
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result  import ToolResult
```

**One more thing that is easy to miss:** `3.20.0.dev1` also raises the Python
floor from 3.10 to 3.11. If your `pyproject.toml` says `requires-python =
">=3.10,…"`, `uv lock` fails with an unhelpful resolver error until you raise it.

Nothing else in this pattern changed — not the ordered block, not the response
template, not the scoped instructions. It trained and greeted identically on
both releases.

If you have a larger agent, point a coding agent at the change log and let it do
the rename.
