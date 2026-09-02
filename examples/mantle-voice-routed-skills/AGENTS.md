# Notes for coding agents

This directory is a **Rasa Mantle** agent (Skills / `rasa.mantle`). It is not a
CALM flows project: there is no `domain.yml`, no `data/flows.yml`, and no
`rasa_sdk` action server. Do not add them.

## Layout

```text
agent.yml                 identity, persona, voice wiring
integrations.yml          LLM provider and channels (ASR/TTS live here)
memory.yml                PROJECT memory — session.project.*
responses.yml             project-level responses
lib/bank.py               in-memory demo bank and the voice normalisers
tools/profile.py          GLOBAL tools, available to every skill
skills/<skill>/skill.md   instructions + frontmatter
skills/<skill>/memory.yml skill-scoped memory schema
skills/<skill>/tools.py   skill-local tools (auto-discovered)
```

## Rules that bite

- **`rules:`, `references:`, `name:` and `description:` are TOP-LEVEL keys in
  `agent.yml`**, siblings of `agent:`. Nested inside it they parse fine and are
  silently discarded.
- **`session.*` is not substituted in instruction prose.** Use
  `@memory.<namespace>.<entry>`, or put the branch in a top-level `if:`.
- **`if:` only works at the top level of a skill body.** Indented inside an
  `instructions:` scalar it stays prose.
- **Tools write memory with the bare key** — `context.memory.set("amount", …)`,
  never `"transfer_money.amount"`.
- Scaffold new projects with `rasa init --engine mantle`.

## Voice

ASR and TTS are configured in `integrations.yml` under
`channels.inspector`, and named again in `agent.yml`'s `voice:` block. Both must
agree. A provider Rasa does not ship is referenced by dotted path rather than
by name.

In this project both halves name the router — `voicerouter.RoutedASR` and
`voicerouter.RoutedTTS` — so `agent.yml` never mentions a vendor. Vendors are
the `providers:` list in `integrations.yml`, in preference order. To change who
speaks, edit that list or `make stack STACK=<name>`; do not touch `agent.yml`.

The live `integrations.yml` is a copy of one of the files in `stacks/`. If you
edit it directly, `make stack` will refuse to overwrite your work — save it as
`stacks/<name>.yml` instead.
