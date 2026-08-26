# Session-start personalization

    Author:        Daksh Varshneya
    Assessed on:   2026-08-26
    Assessed by:   Rod Rivera
    Verified with: rasa-pro 3.19.0.dev7, Python 3.11+, uv
    Audience:      Practitioners building Maestro agents who want every conversation personalized
    Time:          15–20 minutes

Personalize **every** conversation — greet the customer by name and reuse their
profile across all skills — by resolving identity once, at session start, into
shared project memory. No per-skill lookups, no relying on the router to catch a
greeting.

The mechanism is small and channel-agnostic. This directory is a minimal,
runnable agent that does nothing *but* demonstrate it: a session-start profile
lookup, a personalized greeting, and one downstream skill (`view_transactions`)
that reuses the identity without any lookup of its own.

## How it works

The agent's **first message does not come from routing.** At session start the
engine deterministically activates a bundled, engine-managed skill named
`default_session_start` and utters its `utter_greet` response — before the user
types anything. A project skill with the **same id overrides the bundled one**,
so we replace it with an ordered block that runs a lookup first, then greets:

```
:::ordered_block id=main
steps:
  - id: identify
    execute_tool: get_customer_profile   # writes name/tier/… to project memory
  - id: greet
    action: utter_greet                  # interpolates those values
:::
```

`get_customer_profile` writes the profile into **project memory**
(`session.project.*`), which every other skill can read. The greeting response
interpolates those fields, and a global rule in `agent.yml` tells the agent to
keep using the name. `view_transactions` then reads `session.project.customer_name`
and `session.project.default_account_*` to greet by name and offer the usual
account first — proving the "every conversation" claim.

```
session opens
  └─ engine fires default_session_start (engine-managed, deterministic)
       ├─ get_customer_profile  → writes session.project.{customer_name,tier,…}
       └─ utter_greet           → "Good morning, Jordan! Always great to see a Premier member…"
  └─ user: "show my transactions"
       └─ view_transactions reads session.project.* → "Want your usual Everyday Checking, Jordan?"
```

## What it covers

| Piece | File |
|---|---|
| Project (cross-skill) memory schema | `memory.yml` |
| Session-start override + lookup + greeting | `skills/default_session_start/` |
| Downstream reuse of the seeded identity | `skills/view_transactions/` |
| Persona + "address by name" global rule | `agent.yml` |

## Quick start

```bash
cp .env.example .env          # then fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
uv run rasa train
uv run rasa inspect
```

Open the conversation with a greeting: the agent's first line should address you
by name. Then ask for transactions — it offers your usual account first.

## Required secrets

- `RASA_LICENSE` — free Developer Edition key
- `OPENAI_API_KEY`

Names only; never commit values. See `.env.example`.

## Four non-obvious facts this pattern encodes

1. **The opener is a skill, not routing.** `default_session_start` is
   engine-managed and fires deterministically at session start. Override it by id;
   the engine auto-inherits `engine_managed` onto your override.
2. **Tools write project memory with the bare key** (`context.memory.set("customer_name", …)`),
   not `"project.customer_name"` — the prefixed form is rejected at train time as
   an undeclared memory write. Project memory is declared flat in the root
   `memory.yml` and resolves to `session.project.*`.
3. **`session.*` belongs only in `if:` conditions.** For a live value inside
   instruction prose, use a `@memory.<namespace>.<entry>` token (see
   `view_transactions/skill.md`); a raw `session.*` reference in prose is rejected.
4. **`if:` branches must be mutually exclusive.** Overlapping conditions all
   render together and the model sees conflicting instructions. The account
   branches here split cleanly on whether a usual account is on file.

## Notes on this contribution

Contributed by [Daksh Varshneya](https://github.com/dakshvar22) against the
previous catalog pin, `3.19.0.dev5`. Brought onto the current pin during review:
the tool imports moved from `rasa.mantle.tools.*` to `rasa.calm_v2.tools.*`,
which is the module the engine actually ships — the Mantle documentation uses
the other name, and it does not resolve. Re-verified at dev7 (install,
`validate_project`, `rasa train`) by the maintainer named above.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
