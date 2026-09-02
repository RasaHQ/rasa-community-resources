---
name: mantle-tools-and-memory
description: >
  Write Rasa Mantle tools (Python) and design memory scoping. Use when adding
  a tool, when a tool isn't discovered, when deciding local vs shared tools,
  or when choosing project memory vs skill memory.
---

# Tools and memory — the scoping model

## The two scopes, one sentence each

- **Project memory (`memory.yml`, repo root):** facts that outlive a single
  skill — identity, preferences, session state. Every skill reads and writes
  it. **Tool-written only**: `llm_settable: true` here is rejected by the
  engine at validate time.
- **Skill memory (`skills/<id>/memory.yml`):** one skill's working state,
  under `schema: public:`. This is where `llm_settable: true` is allowed.

Rule of thumb: if a later skill could skip work because of it (customer id,
authenticated flag, chosen language) → project memory, set by a tool. If it
only matters until this skill finishes (which account they asked about) →
skill memory, settable by the LLM.

## Writing a tool

Always import from the project's shim, never from `rasa.*` directly:

```python
"""LOCAL tool for check_balance — reading a balance is this skill's job alone."""
from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool


@tool(description="Return the balance of one of the signed-in customer's accounts.")
async def fetch_balance(account_number: str, context: ToolContext = None) -> ToolResult:
    """Look up a single account balance.

    Args:
        account_number: The account number to read.
    """
    customer_id = context.memory.get("project.customer_id") if context else None
    if not customer_id:
        return ToolResult(llm_response={"ok": False, "error": "not_authenticated"})

    account = lookup(customer_id, account_number)
    if account is None:
        return ToolResult(llm_response={"ok": False, "error": "account_not_found"})

    if context is not None:
        context.memory.set("account_number", account_number)  # skill scope

    return ToolResult(llm_response={
        "ok": True, "account_number": account_number,
        "balance": account.balance, "currency": "GBP",
    })
```

The load-bearing facts:

- **Discovery is by the `_tool_description` attribute the `@tool` decorator
  sets** — where you import the decorator from makes no difference, which is
  why the `lib/engine.py` shim is safe.
- Tools are `async def`, take typed args plus `context: ToolContext = None`,
  and return `ToolResult(llm_response={...})`.
- `context.memory.get("project.<field>")` reads project memory;
  `context.memory.set("<field>", value)` writes this skill's scope.
- Return **structured dicts with an `ok`/`error` shape**, never prose. Error
  values like `"not_authenticated"` become branch points in skill prose
  ("If it returns `not_authenticated`, tell the caller you need to verify
  them first"). Include recovery data on errors (e.g. `known_accounts`).

## Local vs shared

- `skills/<id>/tools.py` — tools only that skill uses. No registration needed.
- `tools/` (project root) — tools used by 2+ skills; each consuming skill
  lists them under `import_tools:` in its frontmatter. Document the choice in
  the docstring ("shared with other skills, so it is imported rather than
  living in this skill's folder").

## Authority pattern (the one worth copying everywhere)

Make ONE tool the authority for each invariant, and let skills defer to it:
the balance tool checks authentication itself by reading
`project.customer_id`, so no skill can leak a balance by forgetting a check —
the prose then says the tool "is the authority on whether the caller is
verified." Guardrails in tools are enforced; guardrails only in prose are
requests.

## Verify

- `python3 scripts/lint_mantle.py --check project-memory-writes`
- `make validate` (engine-level: rejects root `llm_settable`, missing tools,
  bad constraints)
