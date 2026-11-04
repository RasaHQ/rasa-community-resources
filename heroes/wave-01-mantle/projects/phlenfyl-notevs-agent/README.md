# notevs-agent — a Mantle agent for your VS Code notes

```text
Author:        Damilola P
Assessed on:   2026-10-22
Assessed by:   Damilola P
Verified with: rasa-pro 3.19.0.dev5, Python 3.10-3.13, uv
Wave:          wave-01-mantle
Audience:      Developers building tool-calling Mantle agents against a local service
Time:          20–30 minutes (uv sync + first chat), plus ~12 minutes for ./retest.sh
```

A local, Rasa Mantle-powered conversational agent for talking to your
[NoteVs](https://github.com/phlenfyl/vsnotes) notes from a chat panel
docked inside VS Code.

Local-only. Tool calls only succeed while VS Code has a project open with
the NoteVs extension active (it's the source of truth for notes — no
cloud, no database) — but you don't need that running to see the agent
itself work; see "Two ways to try it" below.

This is a frozen snapshot of the agent's dev repo, pinned per
[`docs/SNAPSHOTS.md`](../../../docs/SNAPSHOTS.md) to what's committed
here (`pyproject.toml` + `uv.lock`), not migrated forward with the rest
of the catalog.

## Engine: Mantle, on `rasa-pro==3.19.0.dev5`

`agent.yml` + `skills/*/skill.md` + `tools/` is Mantle's project layout;
`rasa init --engine mantle` produces the same shape from scratch.

## Two ways to try it

**1. Standalone, no NoteVs needed** — the fastest way to see the agent
itself: routing, skills, tool-call attempts, the session-start behavior
below. Follow "Running this project", then either talk to it over the
REST webhook or run `rasa inspect --debug` for a full turn-by-turn trace.
Any note-related tool call will correctly *attempt* the call and report
back "NoteVs doesn't seem to be running" rather than crash — you'll see
real orchestration, just not real note data.

**2. With NoteVs running** — install NoteVs from the VS Code Marketplace,
open any folder, create a note or two, then point this project's `.env`
at the same Groq/Rasa credentials and run it standalone while NoteVs is
open in another window. Tool calls now return real note data.

## How the pieces fit together

```
VS Code (NoteVs extension)
  └─ localhost:37492   NoteVs MCP server (extension/src/mcpServer.ts)
       └─ /call   ← plain REST, used by tools/notevs_tools.py below

notevs-agent (this project)
  └─ tools/notevs_tools.py → 10 @tool async functions, each a thin POST to
     http://localhost:37492/call, forwarding which project folder the
     conversation belongs to (NOTEVS_FOLDER_PATH env var) both as a request
     arg and into real declared project memory (memory.yml) — the request
     arg is what keeps each call correct when multiple VS Code windows are
     open at once; the memory mirror just makes it inspectable.
  └─ agent.yml, skills/*/skill.md → agent persona + rules + 4 skills
     (note_management, notes_qa, reminders_and_export, plus
     default_session_start — see below), each import_tools-ing the subset
     of notevs_tools.py it needs, with tool_constraints:
     requires_confirmation on every destructive/external tool
     (delete_note, export_to_notion, export_to_obsidian, set_reminder).
```

## What this project found

Each claim below is re-checked by `./retest.sh`; the run and its output
are under "Evidence" further down.

- **The session-start turn swallows the user's first message.**
  Mantle's built-in `default_session_start` skill only ever greets — its
  own description promises to "handle the first request" too, but its
  steps don't. `skills/default_session_start/skill.md` here overrides it
  with a single `noop` step straight to `END`, so the very first real
  message goes to the LLM router and can activate the right skill in the
  same turn. *Reproduced 2026-10-22:* 3/3 first messages routed with the
  override, 0/3 without it. Whether the activated skill then calls its
  tool depends on the model — see the caveat under "Evidence".
- **Correction: `inspector.enabled: true` does not crash `rasa run`.**
  An earlier version of this README blamed an `EADDRINUSE` crash on
  `0.0.0.0:5005` (2026-08-18) on enabling the inspector channel next to
  `channels.rest`. The 2026-10-22 retest did not reproduce that: both
  channels loaded and the server stayed up. The actual cause was that
  the NoteVs extension's own agent was already listening on 5005, so a
  second `rasa run` on the default port could not bind. If you run this
  project while NoteVs's agent is up, pass a different `--port`.
  Inspector stays off here only because nothing in this project uses
  Mantle's voice channel.
- **`memory.yml`** declares real, framework-visible project memory
  (`folder_path`). A project-root `memory.yml` is picked up by filename,
  and tools in skills with no `memory.yml` of their own write it as
  `project.folder_path`. Without it, `rasa train` refuses the project
  (`calm_v2.validation.tools.undeclared_memory_write`).
  *Reproduced 2026-10-22.*
- **Groq model availability shifts under you.** This project was
  re-pinned mid-build after Groq discontinued `qwen/qwen3.6-27b`
  (confirmed via a live `model_not_found` error and a live
  `GET /openai/v1/models` check against the account's actual key) in
  favor of `qwen/qwen3.8-27b`. Docs pages aren't ground truth for what a
  given account can actually call — the models endpoint is.

## Evidence

Re-run on 2026-10-22 against the installed engine, `3.19.0.dev5`
(Python 3.12.13, macOS arm64), with Groq `qwen/qwen3.8-27b`, from the
commit that adds this section. Full output: [`evidence.txt`](evidence.txt).

```bash
uv sync                 # installs the pinned engine from uv.lock
cp .env.example .env    # RASA_LICENSE + GROQ_API_KEY
./retest.sh             # ~12 min; writes evidence.txt
```

`retest.sh` trains throwaway copies of this folder and serves them on
port 5055, so it never touches `models/` or a NoteVs agent on 5005. Tool
calls go to an unreachable NoteVs URL on purpose, so no real notes are
read. Each chat run sends `list my notes` as the first message of three
brand-new conversations, 65 s apart (Groq's free tier allows 7k input
tokens a minute and one Mantle call is ~3k). For every LLM call it
prints what came back, or the provider error.

| Claim | Copy under test | Expected | Observed |
| --- | --- | --- | --- |
| Session start | as committed | first message routed to a skill | 3/3: `activate notes_qa` |
| Session start | `skills/default_session_start/` removed | built-in greeting consumes the message | 3/3: `greet` step only, no skill or tool; replies like "Hey, I'd like to see a list of my current notes." |
| Inspector + REST | `channels.inspector.enabled: true` | old claim: `EADDRINUSE` crash | **no crash**: both channels loaded, server stayed up (the 2026-08-18 crash was port 5005 already taken; see correction above) |
| Project memory | as committed | tools write `project.folder_path` | slot set to `NOTEVS_FOLDER_PATH` in the 2 turns that ran a note tool |
| Project memory | `memory.yml` removed | write rejected | `rasa train` exits 1: `calm_v2.validation.tools.undeclared_memory_write` |

**Caveat — model behaviour, not engine behaviour.** In the "as committed"
runs, `notes_qa` called `list_notes` in 2 of 3 tries. In the third, the
model answered with four note titles it made up instead of calling the
tool. Earlier runs the same day also hit Groq `tool_use_failed` (a
malformed `activate` call) and per-minute rate limits; both end the turn
with an empty reply. The router behaviour above held in every run whose
LLM call succeeded.

**Groq model pin:** every run above used `qwen/qwen3.8-27b`, so the
current pin works. The earlier `qwen/qwen3.6-27b` retirement is from the
author's notes and was not re-checked.

The source-level memory check (no licence or LLM needed) gives the same
answer: in `3.19.0.dev5`, `memory.yml` is in the engine's
`V2_SNAPSHOT_SOURCE_FILES`, `MemoryManager.set` resolves `folder_path`
to `project.folder_path` from each of the three skills, and the same
write raises `MemoryWriteError` when the project schema is empty.

## LLM provider

Groq, OpenAI, or Anthropic — `set_llm_provider.py` rewrites
`integrations.yml`'s `llm:` block on every `start.sh` run, from the
`LLM_PROVIDER` env var (default `groq`; set alongside the matching API
key in `.env`). `provider: groq` isn't one of Rasa's named wrappers, but
it goes through the same generic LiteLLM passthrough `openai`/`anthropic`
use. Default models: Groq `qwen/qwen3.8-27b` (check
https://console.groq.com/docs/models for whatever's current and confirm
it supports tool calling well — this agent's entire job is calling tools
correctly; `reasoning_effort: none` turns off this model's default
thinking mode, which otherwise leaks its reasoning trace into chat
replies), OpenAI `gpt-4o-mini`, Anthropic `claude-haiku-4-5-20251001`.

## Running this project

```bash
uv sync
cp .env.example .env
# fill in .env — LLM_PROVIDER (groq/openai/anthropic, default groq), the
# matching API key, and RASA_LICENSE
./start.sh
```

Then either:
- `curl -X POST http://localhost:5005/webhooks/rest/webhook -H "Content-Type: application/json" -d '{"sender": "test", "message": "list my notes"}'` — a single message, brand-new session, no priming. You should see a real skill activation in the response, not a generic greeting.
- Or, for a full visual trace: stop that server and run `rasa inspect --debug` instead — opens an interactive debug UI in your browser showing every turn, LLM call, and tool call live.

## How NoteVs end users get the agent running (no terminal at all)

1. Get Python 3.10–3.13 on their machine (a normal dev prerequisite, same
   as needing Node for a JS extension).
2. In the NoteVs extension: sidebar → gear icon → Settings → **Agent**
   section → pick a provider (Groq, OpenAI, or Anthropic), paste that
   provider's API key, and a Rasa license key.
3. That's it. The moment both keys are saved, the extension extracts its
   own bundled copy of this agent into per-user global storage, creates a
   venv, installs `rasa-pro`, and starts `rasa run` with the credentials
   injected as env vars — all automatically. Logs land in the "NoteVs
   Agent" Output channel if anything needs debugging.
