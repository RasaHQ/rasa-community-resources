# Sterling — Tool Scope and Memory Scope in Rasa Mantle

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners deciding where a tool or a memory field belongs
Time:          30–45 minutes
```

A small Meridian Bank agent that exists to answer four questions:

1. When should a tool be **local** to a skill, and when should it be **global**?
2. What belongs in **project memory** rather than a skill's own memory?
3. What is the difference between **public** and **private** skill memory?
4. What makes a skill folder **portable** to another agent?

It is deliberately three skills and text-only. The subject is architecture, not
surface area.

## The scenario

You call your bank, prove who you are, and get transferred — and the next
department asks you to prove who you are all over again. That happens because
nothing is shared between the two systems.

Sterling fixes it in the way Mantle intends: `authenticate` writes
`customer_id` and `authenticated` into **project memory**, and every later skill
reads them. Verify once, then check a balance and send money without
re-authenticating.

## Quick start

```bash
cp .env.example .env      # add RASA_LICENSE and OPENAI_API_KEY
make install
make train
make chat
```

Then run this exact conversation — it is the transcript this project was
verified against:

```text
you  hello
bot  Hello! What can I assist you with today?

you  my passphrase is bluebird
bot  Welcome back, Dana Okafor! You are now signed in.

you  what is the balance on 10029384
bot  The balance on account 10029384 is 2418.55 GBP.

you  send 25 pounds to Sam Rivera
bot  To confirm, you want to send 25 pounds to Sam Rivera. Is that correct?

you  yes, confirm
bot  25 pounds have been sent to Sam Rivera.
```

You give the passphrase exactly once. The balance and the transfer both run
without re-verifying, because `authenticate` wrote `customer_id` into project
memory and their tools read it back.

## The two tool scopes

```text
tools/customer.py                 GLOBAL  get_customer_info
skills/authenticate/tools.py      LOCAL   verify_passphrase
skills/check_balance/tools.py     LOCAL   fetch_balance
skills/transfer_money/tools.py    LOCAL   make_transfer
```

**Local tools** live in the skill's own folder and are auto-discovered. No
import, no registration. `verify_passphrase` is local because checking a
passphrase is the authenticate workflow — no other skill should ever call it.

**Global tools** live in a Python file at the project root and are named in a
skill's `import_tools:`. `get_customer_info` is global because it passes all
three tests:

| Test | `get_customer_info` |
| --- | --- |
| More than one skill calls it? | Yes — `check_balance` and `transfer_money` |
| Skill-agnostic? | Yes — it does not know why it was called |
| About the end user, not one workflow? | Yes — it returns the customer profile |

Fail any test and the tool should stay local.

The import is explicit on purpose. A year later, when you lift
`skills/check_balance/` into a different agent, its `import_tools:` line tells
you exactly what else has to come with it. Nothing has to be discovered by
reading the code.

## The three memory scopes

```text
memory.yml                          PROJECT   authenticated, customer_id,
                                              preferred_language
skills/authenticate/memory.yml      PUBLIC    verification_method
                                    PRIVATE   passphrase_attempts
skills/transfer_money/memory.yml    PUBLIC    amount, payee_name,
                                              transfer_confirmed
                                    PRIVATE   transfer_reason  (pii: true)
```

**Project memory** is for facts about the session and the end user. Every skill
can read and write it. This is the layer that stops the caller re-authenticating.

**Public skill memory** is this skill's working state, readable by other skills.

**Private skill memory** is readable only by the owning skill. `transfer_reason`
is marked `pii: true` and stays inside `transfer_money`. The boundary is enforced
by the runtime — it is not a convention, and the model cannot talk its way past
it.

Project memory persists for the whole session, which is what makes the caller's
verification stick: `authenticate` writes `authenticated` once, and every later
skill reads it instead of asking again.

A word of warning about `immutable: true`, because the name invites a wrong
guess. It does not mean write-once-then-frozen. It means the field can never be
written at runtime at all — it is for constants seeded by `initial_value`. Put
it on `customer_id` and authentication itself fails, with
`Memory field 'customer_id' is immutable and cannot be overwritten`.

## Why this makes a skill portable

A skill folder is self-contained when three things are explicit: the tools it
owns, the tools it imports, and the memory it touches. All three are declared,
so moving `skills/transfer_money/` into another agent is a copy plus whatever
`import_tools:` names. That was the design goal behind splitting tools and
memory this way in the first place.

## Project layout

```text
agent.yml                 persona and rules
integrations.yml          LLM and channels
memory.yml                PROJECT memory
lib/engine.py             engine imports, resolved in one place
lib/directory.py          in-memory demo data (no database to set up)
tools/customer.py         GLOBAL tools
skills/<skill>/skill.md   instructions + frontmatter
skills/<skill>/memory.yml public / private skill memory
skills/<skill>/tools.py   LOCAL tools
```

## Demo data

One customer, so the walkthrough is predictable:

| Field | Value |
| --- | --- |
| Name | Dana Okafor |
| Customer id | MB-4417 |
| Passphrase | `bluebird` |
| Accounts | `10029384` (current), `10029385` (savings) |
| Payee | Sam Rivera |

## A note on the import path

Tools here import from `rasa.mantle`. The Mantle documentation shows
`rasa.mantle`, which is the module name after an upcoming rename — it does not
exist in any release published so far, including 3.19.0.dev7 and 3.19.1. When a
release ships `rasa.mantle`, change the import line and nothing else.

## Commands

```bash
make install    # uv sync --prerelease=allow
make train      # rasa train
make chat       # rasa inspect
make scopes     # print every tool and memory field with its scope
make validate   # validate the project without training
make clean      # remove models and caches
```

`make scopes` is the quickest way to see the architecture:

```text
GLOBAL tools (project root; named in a skill import_tools)
  get_customer_info
LOCAL tools (skill folder; auto-discovered)
  authenticate/verify_passphrase
  check_balance/fetch_balance
  transfer_money/make_transfer
PROJECT memory (every skill reads and writes)
  authenticated, customer_id, preferred_language
SKILL memory (public = other skills may read; private = never)
  authenticate:    public verification_method   private passphrase_attempts
  transfer_money:  public amount, payee_name    private transfer_reason
```
