# Ora — a Rasa Mantle agent on HubSpot CRM

```text
Author:        Rod Rivera
Assessed on:   2026-08-26
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev1, Python 3.11+, uv
Audience:      Practitioners wiring an agent to a system of record
Time:          45–60 minutes
```

A support agent that looks a customer up in HubSpot, reads their open tickets,
and writes the conversation back to their timeline — over the HubSpot CRM v3
REST API.

The subject is not HubSpot. It is what changes when a tool stops being a local
function and starts being a call across a **trust boundary**: credentials,
timeouts, rate limits, and the difference between "no such customer" and "the
CRM is down".

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
5. `make crm-check EMAIL=you@yourcompany.com` before running the agent

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

## Commands

```bash
make install    # uv sync --prerelease=allow
make mock       # run the mock CRM (second terminal)
make train      # rasa train
make chat       # rasa inspect
make crm-check  # call the CRM directly and print what comes back
make clean      # remove models and caches
```

## What comes next

HubSpot also exposes an MCP server, and Mantle has an `mcp_servers:` block in
`integrations.yml`. In `3.19.0.dev7` that block is parsed but has no runtime
consumer yet — the Mantle engine never connects to it — so this tutorial uses
REST. When MCP lands, the same three skills can keep their instructions and swap
`tools/crm.py` for imported remote tools.
