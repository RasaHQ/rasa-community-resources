# Ora — a Rasa Mantle agent on HubSpot CRM

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners wiring an agent to a system of record
Time:          45–60 minutes, plus 20–30 for the MCP chapter
```

A support agent that looks a customer up in HubSpot, reads their open tickets,
and writes the conversation back to their timeline — over the HubSpot CRM v3
REST API.

The subject is not HubSpot. It is what changes when a tool stops being a local
function and starts being a call across a **trust boundary**: credentials,
timeouts, rate limits, and the difference between "no such customer" and "the
CRM is down".

Part two then swaps the transport out from under those same three skills — REST
becomes MCP — and shows that their instructions do not change. See
[Part two: the same agent over MCP](#part-two-the-same-agent-over-mcp).

## You do not need a HubSpot account

The project ships a mock CRM that speaks the real HubSpot request and response
shapes, including the exact `INVALID_AUTHENTICATION` body HubSpot returns. Run
it in a second terminal and everything works offline.

Pointing the same agent at real HubSpot is two environment variables. The
client code does not change.

## Quick start

New to this? **[SETUP.md](SETUP.md)** is the same thing with every menu path
spelled out and a check after each step.

```bash
make env                  # copies .env.example, then add RASA_LICENSE + OPENAI_API_KEY
make install
make mock                 # second terminal: the mock CRM on :8787
make crm-check            # three green ticks before you go further
make train
make chat
```

Then:

```text
you  hi, it's dana.okafor@example.com
bot  Thanks Dana. I have your account with Okafor Logistics.

you  what tickets do I have open?
bot  Two. Invoice 4471 shows the wrong VAT rate, waiting on us. And a request
     to add a second admin, waiting on you.

you  log that I called about the invoice
bot  Noted on your timeline.
```

## Switching to real HubSpot

**[SETUP.md](SETUP.md) walks through this one step at a time**, including where
each menu lives and what to do when a scope is missing. The short version:

1. HubSpot → **Development → Legacy apps → Create legacy app → Private**
   (you must be a super admin)
2. Scopes: `crm.objects.contacts.read`, `tickets`, `crm.objects.notes.write`
3. Copy the token from the app's **Auth** tab into `HUBSPOT_ACCESS_TOKEN`
4. Comment out `HUBSPOT_BASE_URL` so it falls back to `https://api.hubapi.com`
5. `make crm-check EMAIL=you@example.com` before running the agent

Nothing else changes. That is the point of keeping the base URL configurable.

## Where the CRM lives in the project

```text
lib/hubspot.py              the REST client — the only place HTTP happens
tools/crm.py                GLOBAL tool: find_contact_by_email
skills/identify_customer/   uses the global tool, writes project memory
skills/check_tickets/       LOCAL tool: list_open_tickets
skills/log_interaction/     LOCAL tool: add_timeline_note
memory.yml                  PROJECT memory: contact_id, contact_email, contact_name
scripts/mock_hubspot.py     stand-in CRM so the tutorial runs with no account

mcp_variant/                part two: the same skills, transport swapped
  integrations.yml          adds the mcp_servers: block
  skills/*/skill.md         same prose, import_tools: mcp/<server>:<tool>
scripts/mcp_crm_server.py   an MCP server in front of the same lib/hubspot.py
scripts/prove_mcp_swap.py   the credential-free proof of the swap
```

`find_contact_by_email` is **global** because it passes all three tests from the
[tool scope tutorial](../rasa-tools-and-memory-tutorial/README.md): more than
one skill calls it, it is skill-agnostic, and it is about the end user rather
than one workflow. Reading tickets and writing notes stay **local** — each
belongs to exactly one skill.

## The part worth copying

`lib/hubspot.py` never raises a bare exception at the model. Every failure is
mapped to a stable reason string:

| Reason | When |
| --- | --- |
| `crm_not_configured` | no access token in the environment |
| `crm_auth_failed` | HubSpot rejected the token itself (401) — wrong or revoked |
| `crm_forbidden` | token is valid, the app lacks the scope (403) — tick a box |
| `crm_timeout` | no response within 10 seconds |
| `crm_unreachable` | DNS, TLS, connection refused |
| `crm_rate_limited` | HubSpot returned 429 |
| `not_found` | the object does not exist |

The tools turn those into `ToolResult` values, and the skill instructions branch
on them. That is what stops the agent inventing an answer when the CRM is down:
it has a fact to report instead.

A customer who genuinely is not in the CRM is **not** an error — it returns
`None`, and the skill asks them to check the address. Confusing "absent" with
"broken" is the most common mistake in this kind of integration.

## The declared step list

Named for what each step teaches, not for the industry it is dressed in.

| Step | Teaches |
| --- | --- |
| `step-01-trust-boundary` | a tool that leaves the process can fail in ways a local one cannot |
| `step-02-failure-taxonomy` | "absent" and "broken" are different facts, and the agent must say which |
| `step-03-tool-scope` | which tools are global, which belong to one skill, and the test that decides |
| `step-04-irreversible-write` | an ordered block plus a runtime confirmation around someone else's system of record |
| `step-05-transport-swap` | the same instructions over a different transport |
| `step-06-transport-limits` | what the new transport takes away: memory, stdio, load-time failure |
| `step-07-channel-shaping` | the narrowest channel decides the shape of the answer |

### Zero overlap with the six-way baseline

[docs/TUTORIAL-TEMPLATE.md](../../docs/TUTORIAL-TEMPLATE.md) records that six
voice projects in this catalog reduce to one list:

```text
scaffold | faq | READ-TOOL | tool-constraints | WRITE-TOOL | second-flow | remaining
```

Strip the industry nouns from both and no step is shared. The baseline teaches
**how to add a tool**; steps 1–4 here teach **what changes when the tool is
across a trust boundary**, and steps 5–7 teach **what changes when the
transport under it is replaced** — a question the baseline cannot ask, because
it has only ever had one transport.

The two lists do not even have `scaffold` in common: this tutorial has no
scaffold step, because a reader arrives at part two with a working agent
already. That is the point of extending a shipped tutorial rather than writing
a new one — the swap is only visible against something that already worked.

### What this composes

- **Composes:** [`tutorials/rasa-tools-and-memory-tutorial`](../rasa-tools-and-memory-tutorial/README.md)
- **The question it answers:** where should a tool live, and what may it read?
- **The question this one answers:** what survives when that tool stops being a
  local function and becomes a call to someone else's process?
- **Taken as an input, not taught here:** tool scope, and the memory model. This
  tutorial assumes you know which tools are global and reuses that judgement
  unchanged across the swap.

## Commands

```bash
make install    # uv sync --prerelease=allow
make mock       # run the mock CRM (second terminal)
make train      # rasa train
make chat       # rasa inspect
make crm-check  # call the CRM directly and print what comes back
make clean      # remove models and caches

make mcp-prove    # prove the transport swap (no licence, no key, no account)
make mcp-server   # run the MCP CRM server on :8931
make mcp-swap     # move the project onto MCP (reversible)
make mcp-restore  # move it back to REST
make mcp-status   # say which transport is live
```

## Part two: the same agent over MCP

This tutorial used to end with a promise:

> HubSpot also exposes an MCP server, and Mantle has an `mcp_servers:` block in
> `integrations.yml`. In `3.19.0.dev7` that block is parsed but has no runtime
> consumer yet — the Mantle engine never connects to it — so this tutorial uses
> REST. When MCP lands, the same three skills can keep their instructions and
> swap `tools/crm.py` for imported remote tools.

MCP has landed, and the promise held. `rasa-pro 3.20.0.dev6` connects to
`mcp_servers:` and resolves `import_tools: mcp/<server>:<tool>` at model load.
The three skills now run against a remote MCP server **with their instructions
unchanged**.

Not "barely changed". Unchanged. Here is the entire difference, all three skills:

```diff
--- skills/identify_customer/skill.md
+++ mcp_variant/skills/identify_customer/skill.md
 import_tools:
-  - find_contact_by_email
+  - mcp/hubspot_crm:find_contact_by_email

--- skills/check_tickets/skill.md
+++ mcp_variant/skills/check_tickets/skill.md
+import_tools:
+  - mcp/hubspot_crm:list_open_tickets

--- skills/log_interaction/skill.md
+++ mcp_variant/skills/log_interaction/skill.md
+import_tools:
+  - mcp/hubspot_crm:add_timeline_note
```

Every changed line is inside the YAML frontmatter. Not one line of instruction
prose moved — the branching on `not_identified`, the `waiting_on_us` wording,
the ordered block, the confirmation constraint, all byte-identical. `make
mcp-prove` asserts that, and fails if it ever stops being true.

The lesson is the one thing a from-scratch MCP tutorial cannot teach: **skill
instructions are written against a tool's name and result shape, not against its
transport.** Change the wire and the prose survives, because the prose was never
about the wire.

Published chapters: **[Instructions Survive the
Transport](https://rasa.community/library/tutorials/crm-transport-swap/)**.

### Try it

```bash
make mcp-prove     # no licence, no API key, no HubSpot account
```

Then run the agent on MCP:

```bash
make mock          # terminal 1: the mock CRM
make mcp-server    # terminal 2: the MCP server in front of it
make mcp-swap      # move the project onto MCP
make train && make chat
make mcp-restore   # put REST back
```

`make mcp-swap` is reversible on purpose: the REST project is the baseline the
swap is measured against, so it stays on disk rather than being replaced.

### What MCP does not do for you

The swap is small, and the temptation is to conclude MCP is free. Three limits,
each of which the engine enforces rather than merely recommends.

**1. An MCP tool has no memory.** A local `@tool` receives a `ToolContext` and
can read and write project memory. An MCP tool does not — the engine says so
itself, in `skill_executor.py`:

> Local tools receive a `ToolContext`; MCP tools dispatch through the
> processor-owned `MCPRuntime`.

So `list_open_tickets`, which read `project.contact_id` out of memory in the
REST version, takes a `contact_id` **parameter** in the MCP version, and the
model fills it from the conversation. The instructions did not change; the
plumbing under them did. If a tool's correctness depends on a value the user
must not be able to influence, that value cannot be an MCP argument — keep that
tool local.

**2. There is no stdio transport.** `MCPServerSpec` requires a `url:` whose
scheme is `http` or `https`, and `MCPServerConnection` only ever builds a
`streamablehttp_client`. A stdio MCP server — the form most desktop MCP clients
speak — cannot be reached by this engine at all. The bundled server is therefore
an HTTP server on loopback.

**3. A missing remote tool is a load-time failure, not a train-time one.**
`parse_mcp_imports` checks the *syntax* of every `mcp/<server>:<tool>` reference
and catches collisions, but it cannot check that the server actually offers the
tool: that needs a live `list_tools`. So `rasa train` passes and the failure
lands at model load, from `MCPRuntime.prepare`:

```text
MCP server 'hubspot_crm' does not expose imported tool 'list_tickets'
```

A typo in an import line is caught late. `make mcp-prove` is what moves that
check back to before you train.

And the guarantees you already had do survive. The `requires_confirmation`
constraint on `add_timeline_note` still fires — `tool_constraints_executor.py`
resolves MCP tools through the same `has_mcp_tool` lookup, so the runtime still
asks before a remote write lands. A constraint is a property of the skill, not
of the transport.

### Channel formatting: the same answer, shaped for where it lands

`integrations.yml` declares two channels, `rest` and `inspector`, and the agent
answers on both. The tool result is identical; what differs is what the reader
can see.

The ticket list is the case that shows it. `list_open_tickets` returns
structured rows — id, subject, stage, created — and the Inspector renders that
happily as several lines. The same several lines pushed through the REST channel
arrive as one blob of text, and read by a voice channel they would be unusable.

That is why the `check_tickets` instructions say

> read back each subject and its stage in plain language

rather than "return the ticket list". The skill is told to produce a spoken
sentence, not a table, because the narrowest channel the agent serves decides
the shape of the answer. Formatting is a skill-level decision made once, not a
per-channel template — which is also why it did not have to change when the
transport did.

## What comes next

Point `mcp_servers:` at HubSpot's own MCP server instead of the bundled one:

```yaml
mcp_servers:
  - name: hubspot_crm
    url: https://mcp.hubspot.com/anthropic
    token: ${HUBSPOT_ACCESS_TOKEN}
```

Two lines, and the same three skills. That is the claim this chapter exists to
make checkable.
