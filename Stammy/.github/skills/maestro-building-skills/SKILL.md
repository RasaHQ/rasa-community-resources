---
name: maestro-building-skills
description: >
  Authors Maestro skills: skill.md instructions, auto-discovered Python tools, and
  the progressive control ladder (tool constraints, scoped instructions, verbatim
  responses, ordered blocks, sub-skills). Use when creating or editing any file under
  skills/, deciding how much control a skill needs, or composing skills together.
license: Apache-2.0
engine: maestro
rasa_version: ">=3.18"
metadata:
  author: rasa
  version: "0.1.3"
  docs-url: https://rasa-2f7eb63d.mintlify.site
---

# Building Maestro skills

A skill is a folder under `skills/` holding one user goal. The only required file is
`skill.md`: YAML frontmatter (metadata + control declarations) and a markdown body
(prose instructions the LLM follows). Tools live in a single `tools.py` next to
`skill.md` — every `@tool`-decorated function in it is auto-discovered, no registration.

**The core discipline is progressive control: write prose first, add control levers
only when observed behavior must become guaranteed behavior. Every lever is additive
— you never restructure what's already written.**

## Workflow

1. Scope the skill — one user goal per skill (see "Scoping").
2. Write `skill.md` with `name`, `description`, and a prose body. No control levers.
3. Write the tools it needs in `tools.py` (see "Tools").
4. Train and converse: `rasa train && rasa inspect`. Treat `rasa train` errors as
   validation feedback (undeclared memory, bad YAML, missing references) — fix and
   retrain before debugging conversation behavior.
5. Observe drift, then add the *narrowest* lever that fixes it (see "The control
   ladder"). Re-test. Repeat.
6. Extract shared behavior into sub-skills only when a second skill needs it.

## Scoping

- **One user goal, clear start and end**: `replace_card`, `check_balance`,
  `book_appointment`. Verb-first `snake_case` names.
- The `description` in frontmatter is what the orchestrator uses to route — write it
  as a routing summary, including trigger phrasings ("lost, stolen, damaged, or not
  received"), not marketing copy.
- Too big: one skill mixing unrelated goals (returns + payments + tracking). Split.
- Too small: a skill that only wraps one utterance or one tool call with no
  conversation. Inline it into the skill that uses it.

## The minimal skill

```markdown skills/card_replace/skill.md
---
name: Card Replace
description: Replace a credit card -- lost, stolen, damaged, or not received
---

Help the customer replace a credit card.

Check whether their account is eligible for replacement. If they have
multiple cards, ask which one. Ask why they need a replacement -- the valid
reasons are lost, stolen, damaged, or not received.

For stolen or not-received cards, offer to lock the card while a new one
ships. Once everything is gathered, ask their shipping preference,
confirm the order, and process the replacement.
```

Write the body like instructions to a competent human agent: what to gather, what
order matters (softly), what to offer when. The skill id is the folder name
(`card_replace`); `name:` is only a display label.

Name tools in plain prose ("then call `lock_card`"), since they are already in the
model's schema while the skill is active. Jump tokens: `@block.<block_id>` for an
ordered block in this skill, `@skill.<skill_id>` for another skill, and
`@memory.<namespace>.<entry>` for a live memory value inline (see "Memory in
prose"). Both block and skill tokens take ids, never display names.

## Tools

```python skills/card_replace/tools.py
from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

@tool(description="Lock a card to prevent further transactions")
async def lock_card(
    card_id: str,
    context: ToolContext = None,
) -> ToolResult:
    """Lock a card to prevent further transactions.

    Args:
        card_id: Card identifier from get_customer_info.
    """
    result = await api.post(f"/cards/{card_id}/lock")
    return ToolResult(llm_response={"locked": True, "card_id": card_id})
```

- Function name = tool name; `@tool(description=...)` = what the LLM sees; type
  hints = input schema; Google-docstring `Args:` = per-argument descriptions.
- `context: ToolContext = None` is injected, invisible to the LLM. Use
  `context.memory.set(key, value)` to write memory (this is what `requires:`
  conditions gate on), `context.send(text)` for immediate deterministic messages.
  Every key you `set` must be declared in a `memory.yml` schema — `rasa train`
  rejects undeclared writes (`undeclared_memory_write`).
- Return `ToolResult(llm_response=...)` — the LLM reads this as the tool's result.
  Write to memory for anything later steps or `requires:` conditions need.
- Tools outside the skill folder need frontmatter declaration:

```yaml
import_tools:
  - get_customer_info        # shared: from tools/ at agent root
```

- A skill-local tool wins over a shared tool of the same name. Resolved once at
  model load.
- To validate or clean a value right after it is written, define
  `run_after_setting_<memory_entry>` in the same `tools.py`. It is an internal
  hook, never offered to the LLM; return a JSON payload with a non-null `error`
  to reject the write and roll it back. Ask for values in prose.

### Interruptions

A running tool is interrupted when the user barges in (or the session times out, or
the client cancels): `asyncio.CancelledError` is raised at the tool's current `await`
and propagates through its helpers. Nothing to wire up.

An interrupted tool leaves **no record of the call** and does **not** advance the step,
so it can run again next turn — while memory it already wrote is kept. Read-only tools
don't care. For irreversible ones:

```python
@tool(description="Execute a money transfer between accounts.")
async def process_transfer(amount: float, context: ToolContext = None) -> ToolResult:
    if ref := context.memory.get("transfer_ref"):
        return ToolResult(llm_response={"ok": True, "reference": ref})   # already ran
    if context.is_cancelled:
        return ToolResult(llm_response={"ok": False, "reason": "interrupted"})
    ref = new_transfer_reference()
    context.memory.set("transfer_ref", ref)          # written before the call
    await bank.transfer(amount, idempotency_key=ref)
    return ToolResult(llm_response={"ok": True, "reference": ref})
```

- `context.is_cancelled` — check immediately before an irreversible operation, and
  between consecutive ones. It guards what comes *next*; checking just to learn that
  the previous `await` was interrupted is redundant (that arrives as an exception).
  Returning early is clean: the call is recorded and the step advances.
- Idempotency key in memory before the call — the only thing that covers an interrupt
  landing *during* the call.
- **Compensating actions** — idempotency prevents double-charge, not undo. If the
  backend may have completed before the interrupt, check on the next turn and run a
  domain-specific reversal in your tool/API; the runtime will not do this for you.
- `except asyncio.CancelledError` — allowed for cleanup, must re-raise, and must be
  quick: the engine waits ~0.5s for an interrupted tool to unwind, then moves on and
  cuts off whatever is still running.

## The control ladder

Add levers in this order. Each row is a symptom you actually observed in testing —
don't add levers speculatively.

| Observed drift | Lever | Where |
|---|---|---|
| Calls a tool before its inputs exist | `tool_constraints` → `requires:` | frontmatter |
| Executes an irreversible action without asking | In-flow prose confirmation + `requires:` on a confirmation memory key (e.g. `order_confirmed`), or `requires_confirmation:` on the tool in `tool_constraints` | body + frontmatter |
| Fixed wording after a gated tool succeeds or fails | `on_success:` / `on_failure:` on the tool + templates in `responses.yml` | frontmatter |
| Follows the wrong branch / mixes workflows | one `if:` marker per case | body |
| Paraphrases wording that must be exact (legal, compliance) | `utter:` triggers + `responses.yml` | frontmatter |
| Skips or reorders steps where order IS the requirement | ordered block | body |
| Enters the skill when it shouldn't | skill-level `requires:` | frontmatter |

### Tool gating and verbatim outcomes

`tool_constraints` gate when tools appear in the LLM schema and when they may
dispatch. Use `requires:` to hide a tool until memory preconditions hold. Use
`requires_confirmation:` with `enabled: true` on irreversible tools to pause
dispatch and resume only after the user confirms via `resolve_tool_confirmation`
(`confirmed=true` runs the stored call; `confirmed=false` cancels it). Nested
`utter_for_confirmation` and `utter_on_user_denial` are optional names of
responses in `responses.yml`: the engine emits a supplied ask (WAIT) or denial
(WAIT); the LLM handles a response whose name is omitted. Use
`requires_confirmation: { enabled: true }` to enable the gate without
engine-owned ask or denial text. Re-calling the gated tool while confirmation is
pending returns an error. Use `on_success:` / `on_failure:` to name verbatim
responses emitted after the tool result (success vs error payload).

```yaml
tool_constraints:
  - lock_card:
      requires: "session.project.selected_card_id"
  - process_card_replacement:
      requires: >
        session.card_replace.order_confirmed
        and session.card_replace.shipping_type
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_ask_replacement_confirmation
        utter_on_user_denial: utter_replacement_cancelled
      on_success: utter_replacement_disclaimer
      on_failure: utter_replacement_failed
```

Placeholders in `responses.yml` bodies (including confirmation ask/denial):

- `{session.<namespace>.<entry>}` — e.g. `{session.project.selected_card_label}`
- `{entry}` — bare memory field; resolved skill-local first, then project scope

Supplied `utter_for_confirmation` / `utter_on_user_denial` names must exist in
`responses.yml` with a non-empty body (validated at train time). Unknown keys
under a tool entry (for example a flat `ask_confirmation:`) are also rejected —
use nested `requires_confirmation`. If a supplied ask resolves to blank text
after placeholder substitution, dispatch fails closed instead of pausing
silently. If a supplied denial resolves to blank text, the engine warns and lets
the LLM respond (same as omitting that name).

`requires:` is a **string** memory expression. The map form
(`selected_card_id: { exists: true }`) is rejected.

In **conditions** (`requires:`, `if:`, `complete_when:`, `utter:` `when:`, `next:`),
every memory reference uses three segments: `session.<skill_id>.<entry>` for a
skill's own memory, `session.project.<entry>` for project-wide memory. A bare key
is rejected at validation with `Unknown name '<key>' in condition expression`, so
`requires: selected_card_id` does not work. Within that form you can write a
truthiness check (`session.project.selected_card_id`), a boolean combination
(`session.card_replace.order_confirmed and session.card_replace.shipping_type`,
`not session.card_replace.fraud_report_filed`), or a comparison
(`session.card_replace.replacement_reason == 'stolen'`). Use a folded `>` scalar
when the expression spans lines.

A closed gate removes the tool from the LLM's schema, so it cannot call what it
cannot see. Every key referenced must be declared in a `memory.yml` schema.
`tool_constraints` are enforced no matter who triggers the tool, the LLM or an
ordered-block `execute_tool:` step.

### Scoped instructions (`if:`)

Deterministic branching without restructuring. Pairs well with a `categorical`
entry in `memory.yml`; the framework strips non-matching paragraphs from the
prompt once the entry is set:

```markdown
if: session.card_replace.replacement_reason == 'stolen'
Tell the customer the card will be locked for their protection.
Confirm, then call lock_card.

if: session.card_replace.replacement_reason == 'lost' or session.card_replace.replacement_reason == 'not_received'
Call check_transactions and review recent transactions with them.
```

A prose `if:` condition is **the rest of that one line**. YAML folding does not
apply here: `if: >` followed by indented lines makes the condition the literal
`>` and turns the condition text into the paragraph body. Keep it on one line,
however long.

There is one marker, `if:`. Write one paragraph per case, each stating its own
condition; `else:` in prose fails to compile. For exclusive either/or routing,
use an ordered block's `next:` branches.

```yaml skills/card_replace/memory.yml
schema:
  public:
    replacement_reason:
      type: categorical
      enum_values: [lost, stolen, damaged, not_received]
      description: Why the card is being replaced.
```

A marker scopes only the paragraph immediately after it (up to the blank line).
Unmarked paragraphs are always visible.

### Memory in prose (`@memory`)

For a **live memory value inside LLM-facing instructions** (unmarked prose, text
under an `if:` body, or ordered-block `instructions:`), use
`@memory.project.<entry>` or `@memory.<skill_id>.<entry>`. Access matches readable
memory while the skill is active (project fields; other skills' **public** fields;
this skill's **public and private** fields). Another skill's private fields and
`@memory.system.*` fail `rasa train`.

At prompt build the engine substitutes the current value (same stringification as
the `### Memory:` section). Unset or unreadable refs stay as the literal token.
Set PII fields become bare `[set]` (the whole token, not `field: [set]`).

Example:

```markdown
Use the already chosen card @memory.project.selected_card_id for this request.
```

Keep `session.*` for structured YAML and conditions (`requires:`, `if:`,
`execute_tool` `parameters:`). Use `{session.*}` in `responses.yml`. Do not put
bare `session.*` in free prose — `rasa train` fails; use `@memory.…` instead.
Incomplete `@memory` lookalikes (for example `@memory.project`) also fail train.

### Verbatim responses (skill triggers)

Exact wording the LLM never touches. Declare triggers in frontmatter; put text in
`responses.yml` (supports `{memory_key}` interpolation):

- **`on: activate`** — fires once when the **owning skill** is activated (routing
  into the skill). Does not fire on ordered-block entry or interrupt resume within
  the same skill.
- **`when:`** — a condition expression, same syntax as `requires:` /
  `complete_when:` (memory as `session.<skill_id>.<entry>`). Fires **once** when the
  condition **first becomes true** after a memory write — not on every turn it
  still holds.

```yaml
utter:
  - utter_recording_notice:
      on: activate
  - utter_stolen_warning:
      when: session.card_replace.replacement_reason == "stolen"
```

Tool outcome utters (`on_success:` / `on_failure:`) are separate: they attach to a
gated tool in `tool_constraints`, not to skill `utter:` frontmatter.

### Ordered blocks — last resort, not first

Most skills never need one. Reach for a block only when the *sequence itself* is the
requirement (compliance, multi-step approval). Prefer the hybrid form — one block
inside prose, referenced with `@block.<id>`:

```markdown
Ask why they need a replacement. Once the reason is recorded, invoke
@block.pick_card to check eligibility and settle which card this applies to.

:::ordered_block id=pick_card
steps:
  - id: check_eligibility
    execute_tool: card_replace_eligibility
  - id: fetch_cards
    execute_tool: get_customer_info
  - id: select_card
    instructions: Show the customer their cards and ask which one needs replacing.
    complete_when: "session.project.selected_card_id"
:::
```

The id is a **fence attribute** (`:::ordered_block id=pick_card`), not a YAML key
inside the body. The body is YAML, so indent with spaces; a tab fails the parse.

Step types: `execute_tool:` (framework calls the tool, no LLM), `instructions:` +
`complete_when:` (LLM converses inside the step), `noop: true` + `next:`
(deterministic routing), `collect:` + `utterance:` (framework collects a value,
`utterance:` naming the question). Note `utterance:`, not `utter:`: a `collect:`
step given `utter:` is parsed as an action step and the collect is dropped.

A block enforces local order only. Users can still interrupt to another skill; the
block resumes at the same step.

## Composition

- `@skill.<skill_id>` in the body runs another skill and the parent resumes
  automatically when it finishes. It takes the target's folder name. A
  user-initiated topic change is parked differently: the engine offers the
  customer a resume rather than resuming on its own.
- A skill's `public` fields are readable by every other skill at any time, so
  there is no export step. Keep `public` small: it is the skill's API.
- Default to small focused skills. Compose when a skill needs another's logic
  mid-conversation (disputes needing transaction lookup).
- The parent must have business logic of its own — a skill that is nothing but
  `@skill.` references is the orchestrator's job, delete it.
- Cross-skill dependencies go through memory, not direct coupling: gate with
  `requires: session.project.authenticated` (a string expression) rather than
  referencing the auth skill.

## Don't

- Don't add control levers the user's requirements don't demand — every lever costs
  conversational flexibility.
- Don't write a fully-controlled ordered block as the starting point; that recreates
  the rigid state machines Maestro exists to replace.
- Don't restate tool results in prose ("the tool returns JSON with...") — the LLM
  sees `llm_response` directly.
- Don't invent frontmatter fields. The complete set is `name`, `description`,
  `requires`, `complete_when`, `import_tools`, `tool_constraints`, `utter`, and
  `disabled`. Unknown keys are ignored rather than rejected, so a typo silently
  does nothing.
- Don't use a bare memory key in any **condition**. `requires:`, `if:`,
  `complete_when:`, `utter:` `when:`, and `next:` branches all take the same
  three-segment form: `session.<skill_id>.<entry>` or `session.project.<entry>`.
- Don't put bare `session.*` in free instruction prose — use `@memory.…` for live
  values there (see "Memory in prose").
- Don't treat `rasa train` as optional. It is the validation gate for undeclared
  memory writes, unknown response names, malformed conditions, and bad `@memory`
  references, and its errors are authoring feedback rather than build noise.

## Further reading

Full Maestro documentation: https://rasa-2f7eb63d.mintlify.site

Fetch `https://rasa-2f7eb63d.mintlify.site/llms.txt` for the page index, or
`https://rasa-2f7eb63d.mintlify.site/llms-full.txt` for every page in one file.
Read the specific page when this file is not enough; do not guess syntax.

Most relevant here:

- [Project structure](https://rasa-2f7eb63d.mintlify.site/reference/project-structure): where a skill folder sits and what may live in it
- [skill.md reference](https://rasa-2f7eb63d.mintlify.site/reference/skill-md): frontmatter properties, body format, jump tokens
- [Conditions](https://rasa-2f7eb63d.mintlify.site/reference/conditions): the expression grammar for requires:, if:, complete_when:, next:
- [Ordered block steps](https://rasa-2f7eb63d.mintlify.site/reference/ordered-block-steps): step kinds, step fields, branching
- [Tools reference](https://rasa-2f7eb63d.mintlify.site/reference/tools): ToolContext, ToolResult, gating, post-write hooks, cancellation
- [memory.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/memory-yml): scopes, types, visibility, access control
- [Progressive control guides](https://rasa-2f7eb63d.mintlify.site/build-guide/tool-constraints): one lever at a time, with worked examples
