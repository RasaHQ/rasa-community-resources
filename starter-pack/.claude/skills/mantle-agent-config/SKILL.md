---
name: mantle-agent-config
description: >
  Author or review agent.yml for a Rasa Mantle project. Use when editing agent
  identity, persona, rules, references, voice settings, or when an agent
  ignores its rules/guardrails despite them being "configured".
---

# agent.yml — the file with the silent failure mode

## The trap this file is famous for

Prompt-tuning keys nested under `agent:` **parse without error and are then
silently discarded**. The engine's spec builder reads them only from the top
level of the file; unknown keys inside `agent:` are ignored. A real catalog
of ~10 projects once carried **39 rules the engine never applied** — no
warning at train time, no error at load, found only by reading the built
prompt. Two independent users discovered it separately.

**Top-level keys (siblings of `agent:`), as of 3.20.0.dev6:**
`name`, `description`, `rules`, `conversation`, `references`, `before_end`,
`tool_timeout`.

`tool_timeout` was added in 3.20.0.dev6 — new top-level keys appear on dev
releases, so after an upgrade, re-check this list against the installed
engine rather than trusting it from memory.

## Correct shape

```yaml
agent:
  id: my-agent                # stable slug
  language: en
  persona: |                  # multi-line, the model's standing identity
    You are <Name>, a concise assistant for <domain>.
    Ask one question at a time and keep answers short.

# --- TOP LEVEL from here down ---
name: <Name>
description: <one line>

rules:
  - "Be polite, clear, and brief."
  - "Never state data that did not come from a tool."
```

## Voice agents

Voice config DOES live inside the `agent:` block:

```yaml
agent:
  id: my-voice-agent
  language: en
  persona: |
    ...
  voice:
    enabled: true
    asr: deepgram                     # built-in name, or a dotted path
    tts: deepgram                     # e.g. voicerouter.RoutedTTS
```

Custom ASR/TTS engines are referenced by dotted import path exactly like any
custom engine class — the class must be importable from the project root.
Voice persona tip observed to work well: instruct short spoken replies ("one
or two short spoken sentences") — long text answers are painful read aloud.

## Review checklist (run through it every time)

1. Every prompt-tuning key at column 0? (`grep -n '^\s\+rules:' agent.yml`
   must return nothing.)
2. Persona says what the agent must NOT invent, and routes it to tools?
3. Rules are short imperatives, not paragraphs?
4. If voice: `voice:` inside `agent:`, engines resolvable?
5. Run `python3 scripts/lint_mantle.py --check agent-top-level-keys` — it
   derives the block's own indentation, so 4-space files don't slip past.
