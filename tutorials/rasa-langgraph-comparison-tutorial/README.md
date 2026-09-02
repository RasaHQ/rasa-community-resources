# LangGraph's customer-support bot, rebuilt in Rasa Mantle

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Anyone comparing agent frameworks, or porting a CALM v1 agent
Time:          60–90 minutes
```

The Swiss Airlines travel assistant from
[LangGraph's customer-support tutorial](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/),
rebuilt as Mantle skills.

It is also a port of Rasa's own
[CALM v1 reimplementation](https://github.com/RasaHQ/calm-langgraph-customer-service-comparison)
of that bot — so it doubles as a worked example of moving a flows-based agent to
skills.

## What it does

Five capabilities, the same five as the original:

| Skill | What the traveller can do |
| --- | --- |
| List Bookings | see the flights they hold |
| Change Flight | move a booking to another flight on the same route |
| Book Hotel | find and book a hotel at their destination |
| Book Car | find and book a rental car |
| Book Excursion | find and book something to do |

## Quick start

```bash
cp .env.example .env      # add RASA_LICENSE and OPENAI_API_KEY
make install
make db                   # builds travel.sqlite from the committed fixture
make train
make chat
```

```text
you  what flights do I have booked?
bot  You have two: LX0112 from CDG to BSL on 30 April, and LX0002 back on 9 May.

you  can you move the first one to later that week?
bot  Here are other CDG to BSL flights that week:
       1. LX0112 — 2 May, 12:09
       2. LX0112 — 4 May, 12:09
     Which would you like?

you  the first one
bot  Change your booking to flight 19256?

you  yes
bot  Done — you are now on the 2 May flight.
```

## No 109 MB download

The original pulls LangGraph's `travel2.sqlite` — **109 MB**, 2.3 million rows —
before anything runs.

This project ships `data/travel_seed.sql`: **50 KB**, the same schema, every row
copied from that database, but only the rows the agent can actually reach — the
demo passenger's booking, both routes they fly so flight search returns real
alternatives, and the ten cars, hotels and excursions.

402 rows instead of 2.3 million. `make db` rebuilds it in under a second, and
the fixture is a diffable SQL file rather than a binary blob, so a change to it
is reviewable.

The demo passenger is `3442 587242` — the same one LangGraph's tutorial uses.

## Status

All five skills verified end to end, with the result checked in the database
afterwards rather than taken from what the agent said:

| Skill | Status |
| --- | --- |
| List Bookings | works |
| Change Flight | works — 13 of 14 scripted runs rebooked correctly |
| Book Hotel | works — booking written to the database |
| Book Car | works — booking written to the database |
| Book Excursion | works — booking written to the database |

Change Flight is the one with a number attached because it was the one that
misbehaved for a long time. The residual failure is ordinary model variance on a
scripted run, not a broken path.

## How the port maps

This is the part worth reading if you have a CALM v1 agent.

| CALM v1 | Mantle | Note |
| --- | --- | --- |
| `flows:` with `steps:` | a skill folder with `skill.md` | one flow, one skill |
| `collect:` | a memory field plus an instruction | or a `collect` step inside an ordered block |
| `action:` (Rasa SDK) | `@tool` async function | no tracker, no `SlotSet`, returns data |
| `next:` / `if:` / `else:` | scoped instructions, or an ordered block | branching that the model *sees*, or ordering the engine *enforces* |
| slots | memory: project, or skill public/private | scope becomes explicit |
| `reset_after_flow_ends: false` | project memory | see below |
| `ask_before_filling: true` | `requires_confirmation:` | the runtime asks, not the prompt |

### The one that pays for itself

The original needed `reset_after_flow_ends: false` on the hotel and car dates,
plus a paragraph of slot description explaining exactly when the model may copy
a date from another flow:

```yaml
- collect: hotel_start_date
  reset_after_flow_ends: false
  description: >
    Only fill this slot when the current user message itself contains an
    explicit date or an explicit same-dates phrase … If the phrase refers to
    the car rental, copy the exact ISO value of slots.car_rental_start_date …
```

In Mantle the trip dates are simply **project memory**. Every skill reads them;
nobody copies anything. "A hotel for the same dates" is a read, and the
instruction shrinks to one line.

That is the general shape of this port: things the flow engine made you say out
loud become structural, and the prose gets shorter.

## Project layout

```text
data/travel_seed.sql       the fixture — 50 KB of real rows
scripts/build_db.py        builds travel.sqlite from it
lib/db.py                  data access, ported from the original's actions/db.py
lib/engine.py              engine imports, resolved in one place
tools/trip.py              GLOBAL: list_flight_bookings, used by three skills
skills/<skill>/skill.md    instructions and control levers
skills/<skill>/tools.py    LOCAL tools
skills/<skill>/memory.yml  public / private skill memory
memory.yml                 PROJECT memory: the trip
```

## Commands

```bash
make install    # uv sync --prerelease=allow
make db         # build travel.sqlite from the fixture
make db-check   # query the database directly, without the agent
make train      # rasa train
make chat       # rasa inspect
make scopes     # print every tool and memory field with its scope
make clean      # remove models, caches and the built database
```

## What the port taught us

One real finding, and three lessons about diagnosis that cost more time than the
port itself.

### Tools run from a snapshot, not from your project directory

Mantle packages the project into a temp directory and executes tools from there,
so a path derived from `__file__` resolves inside that snapshot:

```text
/private/var/folders/…/T/tmpjmv64ut2/mantle_snapshot/travel.sqlite does not exist
```

The database was sitting in the project directory the whole time. Anything that
touches the filesystem needs to resolve paths from the working directory, or
ship inside the project so it travels with the snapshot. `lib/db.py` does the
first and rebuilds from the fixture if the file is missing.

### Three things that looked like framework problems and were not

Recorded because the failure modes are convincing, and because the shape of the
mistake matters more than the mistake:

**A `NameError` that read as a stalled ordered block.** Making a tool
parameterless left two dangling references in its body. The tool raised on every
call, the model said "I encountered an error", and the block looked like it was
refusing to advance. It ran perfectly; the tool inside it did not. *Read the
tool result before theorising about the engine.*

**A test script that ran out of turns.** Binding an `execute_tool` step's
parameters to memory makes the model collect those values first, which adds a
turn. A fixed-length script then ends before answering the runtime's
confirmation, and the database is unchanged — which looks exactly like a failed
booking. With one more turn: 4/4. *A conversation is not a fixed-length script.*

**An error the model reported truthfully.** It said the database had not been
built; a log grep found no such error, so it looked like the model was reciting
an error branch out of the instructions. It was not — the tool really was
failing, on the snapshot path above, and the log simply was not at debug level.
*Absence of evidence in a log is not evidence of absence.*

None of this is a Mantle defect. The snapshot behaviour is worth knowing about,
and is the one thing here worth documenting upstream.

## Credit

The scenario, the database and the five capabilities come from
[LangGraph's customer-support tutorial](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/).
The CALM v1 implementation this is ported from lives at
[RasaHQ/calm-langgraph-customer-service-comparison](https://github.com/RasaHQ/calm-langgraph-customer-service-comparison).
