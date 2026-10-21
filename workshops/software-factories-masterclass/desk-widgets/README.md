# A travel desk behind one MCP tool: the Mantle side, graded offline

sow: software-factories-masterclass-SOW-02

Status: DRAFT for the Thursday 22 October session. Not in the frozen pack that was read on 21 October 12:03Z; added as a routed delta.

A Mantle skill (`project/skills/desk/skill.md`) imports one MCP tool, `mcp/desk:ask_desk_agent`. The MCP server behind it
(`http://127.0.0.1:8951/mcp`) is built separately in the companion example `examples/mantle-desk-widgets-openai-agents`
(not in this folder; until it is merged and pinned, nothing here runs against a server). Behind that tool an OpenAI
agent (the managed Agents API, not the Agents SDK) decides which preconfigured widget to inject and calls three
read-only data tools. The page that draws the widget is the companion's own host page, **not a Mantle feature**.

## What this folder grades

`acceptance/a6_desk_widgets.py` grades what Mantle will load, with the real engine, offline: the skill compiles, it imports the
tool from a configured server on loopback, nothing is gated (the desk only reads), no local tool code exists, and the
instructions never allow a delay claim, keep numbers as they appear in the tool data, name the rate date and refuse to repeat
an earlier answer when the tool returns none.

## Run it (no licence, no key, no network)

From the pack's `factory` folder environment, from this folder:

```bash
MANTLE_PROJECT=$PWD/project PYTHONPATH=../factory ../factory/.venv/bin/python acceptance/a6_desk_widgets.py
../factory/.venv/bin/python grade_variants.py project
```

Expected: 9 tests OK; the baseline is ACCEPT and the eight edited variants are REJECT, each naming its failing check.

## Limits (said aloud in the session)

- The suite reads the skill's wording and the engine's compiled result. It does not show that a model follows the wording.
- Nothing here exercises the MCP server, the widgets, live data, voice or the OpenAI Agents API.
- A flight answer is a live position, never a schedule; keyless public sources have no schedule data.
- The exchange rate is a daily reference rate, not a live market quote.
