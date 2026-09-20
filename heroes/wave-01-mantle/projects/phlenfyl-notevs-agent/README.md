# notevs-agent — a Mantle agent for your VS Code notes

```text
Author:        Damilola P
Assessed on:   2026-09-20
Assessed by:   Damilola P
Verified with: rasa-pro 3.19.0.dev5, Python 3.10-3.13, uv
Wave:          wave-01-mantle
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

- **The session-start turn used to swallow the user's first message.**
  Mantle's built-in `default_session_start` skill only ever greets — its
  own description promises to "handle the first request" too, but its
  steps don't. `skills/default_session_start/skill.md` here overrides it
  with a single `noop` step straight to `END`. Confirmed live (a direct,
  unprimed REST call to a brand-new session) that this lets the very
  first real message reach the right skill and call its tool in the same
  turn.
- **`inspector.enabled: true` in `integrations.yml` crashes `rasa run`.**
  `inspector` is for the separate interactive `rasa inspect` command
  only; enabled alongside `channels.rest`, `rasa run` tries to bind a
  second listener on the same port right after the REST channel's own
  listener has already bound it — an immediate `EADDRINUSE` crash on
  every start. Kept off here; nothing in this project uses Mantle's own
  voice channel.
- **`memory.yml`** declares real, framework-visible project memory
  (`folder_path`) — confirmed against the installed engine's own schema
  loader that a project-root `memory.yml` is auto-discovered by filename
  convention, and that a tool with no memory.yml of its own can still
  write a project-scoped field.
- **Groq model availability shifts under you.** This project was
  re-pinned mid-build after Groq discontinued `qwen/qwen3.6-27b`
  (confirmed via a live `model_not_found` error and a live
  `GET /openai/v1/models` check against the account's actual key) in
  favor of `qwen/qwen3.8-27b`. Docs pages aren't ground truth for what a
  given account can actually call — the models endpoint is.

## Groq model

`integrations.yml` points at `qwen/qwen3.8-27b` via Groq (LiteLLM
passthrough — `provider: groq` isn't one of Rasa's named wrappers, but
LiteLLM supports it, same mechanism `openai`/`anthropic` use). Check
https://console.groq.com/docs/models for whatever's current and confirm
it supports tool calling well — this agent's entire job is calling tools
correctly. `reasoning_effort: none` turns off this model's default
thinking mode, which otherwise leaks its reasoning trace into chat
replies.

## Running this project

```bash
uv sync
cp .env.example .env
# fill in .env with GROQ_API_KEY and RASA_LICENSE
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
