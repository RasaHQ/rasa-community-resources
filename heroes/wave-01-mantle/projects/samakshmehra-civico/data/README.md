# Demo data

Everything the agent knows lives here as JSON, and is loaded into a local
SQLite database (`data/civico.db`, gitignored) the first time a tool runs.
These domain lookups need no network. The conversation and voice layers use
OpenAI and Deepgram respectively.

| File | What it holds |
|---|---|
| `wards.json` | The ward directory — locality, PIN code, ward, zone, ward officer. This is what replaces a geocoder. |
| `routing.json` | The six categories this line accepts, each with its department and target days. |
| `escalation.json` | The three-level escalation ladder. |
| `citizens.json` | Two demo callers, so a known number and an unknown number can both be demonstrated. |
| `complaints.json` | Four seeded complaints: one on time, one overdue, one resolved, one belonging to the other caller. |

## Why `days_ago` and not a date

`complaints.json` stores an age in days, not a calendar date. The seeder turns
it into a real date when the database is created. A complaint seeded with a
hardcoded date is on time in the week it is written and absurdly overdue three
months later; an age stays true. `CIV1002` is always nine days past a
three-day target, which is what makes the escalation flow demonstrable in a
two-minute recording.

## Resetting

Runtime complaints go into SQLite, not back into `complaints.json`. Supporting
callers are stored in `supporting_reports`, separately from resolution notes.
Their callback number can retrieve the shared complaint on a later call.

For an isolated demonstration, set `CIVICO_DB_PATH` to a database file in a new
temporary directory before starting the server. This keeps your existing reports.

    make reset-db

Deletes `data/civico.db`. The next tool call rebuilds it from these files.

## This is fictional

The entire directory belongs to the invented Civico Demo City. Localities,
aliases, landmarks, ward and caller identifiers, officer labels, departments,
contact numbers and target times are fictional.

PIN values such as `000101` (Maplewick) and `000104` (Brookmere) are dummy
six-digit strings. They retain their leading zeros in JSON, lookup and speech
normalisation; they do not represent real postal areas. Callback values such
as `0000000501` (Demo Caller One) and `0000000502` (Demo Caller Two) and
all `0000-000-01xx` helpdesk contacts are non-dialable placeholders.

These values exist only to exercise routing, ambiguity, consent, persistence,
duplicate support and escalation. No routing or service data came from a real
municipal authority, and no report, message or call leaves the demo.
