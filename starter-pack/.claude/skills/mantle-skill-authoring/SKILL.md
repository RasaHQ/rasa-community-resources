---
name: mantle-skill-authoring
description: >
  Write or fix a Rasa Mantle skill.md. Use when creating a new skill, when a
  skill's conditional branches never fire, when memory values appear as
  literal text in replies, or when designing skill activation/routing.
---

# skill.md — three languages in one file

A skill.md is three different languages stacked, and most authoring bugs come
from treating them as one:

1. **YAML frontmatter** — structured config, never prose.
2. **Markdown body** — instruction prose the LLM reads, EXCEPT top-level `if:`.
3. **`:::block … :::` regions** — YAML again; only `instructions:` scalar
   bodies inside them are prose.

## 1. Frontmatter

```yaml
---
name: Check Balance
description: >
  Tell the caller the balance of one account. Activate for balance, how much
  is in my account, or available funds.
import_tools:            # shared tools from the project-level tools/ dir
  - get_customer_info
tool_constraints:        # gate a tool on a memory field being set
  - get_recent_transactions:
      requires: session.view_transactions.selected_account_id
routing:
  engine_managed: true   # for openers like session-start skills
---
```

The `description` doubles as the activation hint — write the trigger phrases
into it ("Activate for X, Y, or Z"), it is how the router matches requests
to skills.

## 2. Body prose — what substitutes and what doesn't

- `@memory.<namespace>.<entry>` — **exactly three dot-separated parts** — is
  substituted with the live value. `@memory.project.customer_name` works;
  `@memory.customer_name` is dead text delivered to the LLM verbatim.
- Raw `session.x.y` in prose is **never substituted**. It belongs in `if:`
  conditions and `tool_constraints`, nowhere else. If you need the value in
  prose, use the `@memory` form.

## 3. Branching — `if:` at column 0 only

```markdown
if: not session.view_transactions.selected_account_id and session.project.default_account_id
The customer has a usual account on file: @memory.project.default_account_label.
Offer that one first by name. If they say yes, set `selected_account_id` via
`set_fields` to @memory.project.default_account_id.

if: session.view_transactions.selected_account_id
Call `get_recent_transactions` for the selected account and present the rows
briefly (date, merchant, amount).
```

- Conditions reference `session.<skill_id>.<field>` (this skill's memory) and
  `session.project.<field>` (project memory), combined with `not` / `and`.
- **An indented `if:` is not parsed as a condition** — it stays instruction
  prose and your branch silently never branches. If you want a conditional
  inside a paragraph, express it in natural language instead.
- Write branch sets that cover the state space: typically
  `not set and have-default` / `not set and no-default` / `set`.

## 4. Deterministic sequences — ordered blocks

For fixed step sequences (e.g. a session opener), skip prose entirely:

```markdown
:::ordered_block id=main
steps:
  - id: identify
    execute_tool: get_customer_profile
  - id: greet
    action: utter_greet
:::
```

## 5. Skill-scoped memory — `skills/<id>/memory.yml`

This is where `llm_settable` belongs (NOT the root memory.yml):

```yaml
schema:
  public:
    account_number:
      type: text
      description: Account the caller asked about.
      llm_settable: true
```

The LLM writes these via `set_fields`; instruct it explicitly in prose:
"set `selected_account_id` via `set_fields` to the matching id from the tool
result" — and name what it must NOT set or invent.

## 6. Style rules that ship in every good skill here

- One skill = one user goal. Local tools in `skills/<id>/tools.py`; anything
  two skills need moves to `tools/` + `import_tools`.
- State the negative space: "Never state a balance in that case", "Do not
  invent accounts". Mantle personas follow prohibitions well when explicit.
- Hand off across skills through project memory, not prose assumptions:
  "`fetch_balance` reads the signed-in customer from project memory, so it is
  the authority on whether the caller is verified."

## 7. Verify

`python3 scripts/lint_mantle.py --check nested-if --check skill-prose` — then
`make validate` for the engine's own view.
