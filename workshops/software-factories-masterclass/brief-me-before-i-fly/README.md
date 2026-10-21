# Brief me before I fly: the Mantle side, graded offline

sow: software-factories-masterclass-SOW-02

Status: DRAFT for the Thursday 22 October session. Not in the frozen pack read on 21 October 12:03Z; added as a routed delta.

A Mantle skill (`project/skills/briefing/skill.md`) imports one MCP tool from a briefing service:
`mcp/briefing:briefing`, called with action `start`, `get` or `revise`. The service
(`http://127.0.0.1:8951/mcp`) starts and continues OpenAI Agents API sessions and returns widget cards that are defined by zeocore.
It is built separately in the companion example in this repository (not in this folder; nothing here runs against a server).
The cards are defined by zeocore and drawn by our renderer where Mantle does not render them. **They are not a Mantle feature.**

The feature specification and the acceptance scenarios for the product are `SPEC-brief-me-before-i-fly-v4.md` and
`ACCEPTANCE-SCENARIOS-v4.md`, with the two JSON schemas, beside this file. The scenarios are the product's contract; the coding agent in the factory never edits them.

## What this folder grades

`acceptance/a6_briefing.py` grades what Mantle will load, with the real engine, offline: the skill compiles; the one tool is
imported from a configured server on loopback; nothing is gated (the briefing only reads); no local tool code exists; and the
instructions keep delay claims to the provider's own status, numbers as they appear in the data, the transfer time as an assumption,
replayed or delayed data said to be so, missing input asked for, no stale value repeated as current, and the cards said to be zeocore's and ours, not Mantle's.

## Run it (no licence, no key, no network)

From this folder, with the pack's pinned interpreter:

```bash
MANTLE_PROJECT=$PWD/project PYTHONPATH=../factory ../factory/.venv/bin/python acceptance/a6_briefing.py
../factory/.venv/bin/python grade_variants.py project
```

Expected: 15 tests OK; the baseline is ACCEPT and the fourteen edited variants are REJECT, each naming its failing check.

## Limits (said aloud in the session)

- The suite reads the skill's wording and the engine's compiled result. It does not show that a model follows the wording.
- Nothing here exercises the briefing service, the cards' renderer, any data provider, voice or the OpenAI Agents API.
- A wording check accepts any edit that keeps the checked phrases: that is why the product has its own acceptance scenarios.
