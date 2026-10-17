# Software factories on Rasa Mantle: a three-hour masterclass pack

    Author:        Rod Rivera (Claude Code)
    Assessed on:   2026-10-16
    Assessed by:   Claude Code: offline, on macOS, Python 3.11 and 3.12, no Rasa licence
    Verified with: rasa-pro 3.21.0.dev5, Python 3.11+, uv
    Audience:      Engineers who build or review agents and want to put an automated check between a coding agent's change and the project the agent changes
    Time:          3 hours in a room; about 90 minutes alone

This is the exercise material for an in-person masterclass on agentic software
factories with Rasa Mantle as the product. A small factory takes a task, lets a
builder (you, or a coding agent such as Claude Code or Codex) change an isolated
copy of a Mantle project, asks the real Mantle engine to grade the result with a
suite the builder cannot edit, and records ACCEPT or REJECT. You run it, break
it, hand it to an agent, and pool what the room's agents did.

The technology-neutral version of the method is the course "Towards Dark
Software Factories" on profrod.ai. This pack is the Rasa version.

## What you will see

- A Mantle project whose confirmation gate is silently gone while the engine
  reports nothing, and the builder's own tests pass. Only the factory's
  acceptance suite catches it (three configurations: `enabled` omitted,
  `enabled: false`, the constraint deleted).
- A rule nested one level too deep under `agent:` that Mantle drops without a
  finding.
- A grader that can be forged, and the second grader (`factory_v2.py`) that
  closes that hole.
- Eighteen recorded runs by two coding agents (nine Codex, nine Claude Code), all
  accepted, with decisions, patches and final messages, so a room can read what
  agents actually did.
- Two changes that each pass alone and fail together, a release bound to the
  tested digest, an independent approver, recovery, and an interval around a
  pass rate.

## What it does not show

Whether a Mantle agent behaves correctly in a conversation. Every check reads
what the engine compiles and validates from the project files; no model call is
made. Whether an agent waits for the caller at run time is a separate
experiment that needs a model and a licence. The eighteen recorded runs are one
attempt per task by two agents on one pre-release engine build; they support
"these runs were accepted" and nothing about a general pass rate.

## Quick start

    cd workshops/software-factories-masterclass/factory
    uv sync --frozen
    uv run python factory.py tasks/a1-block-card.json candidates/block-card-good runs/good           # ACCEPT
    uv run python factory.py tasks/a1-block-card.json candidates/block-card-gate-omitted runs/omitted # REJECT

`uv sync` downloads about 750 MB (the environment is about 708 MB of files). No
`RASA_LICENSE`, no provider key and no network are needed after install. The
exercise runs in a copy of the project; a copied folder is not a sandbox.

## Contents

| Path | What it is |
|---|---|
| `factory/` | The factory, its tasks, protected acceptance suites, candidates, units and recorded agent runs. `factory/README.md` lists each part |
| `openai-mcp/` | An optional offline exercise: an OpenAI agent behind an MCP server that a Mantle skill imports, graded by a protected suite. The reviewer is a stub; the OpenAI path and everything needing a key or licence has not run. `openai-mcp/README.md` says what it shows and what it does not |
| `FACILITATOR.md` | Agenda by the clock, preparation checklist, hard parts, what not to claim afterwards. Placeholders for date, room, headcount and level |

## Pin

`rasa-pro==3.21.0.dev5`, a pre-release. Its configuration schema moves: on
2026-10-15 `3.21.0.dev10` rejected the baseline project this pack uses. Keep the
lock, and rerun the checks before raising the pin.
