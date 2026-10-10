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
months later; an age stays true. `CIV1002` is always eight days past a
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

Localities and PIN codes are real Ghaziabad ones so the demo sounds plausible
to anyone who knows the city. Ward numbers, officer names, phone numbers,
departments and target times are invented. No routing or service data came from
a real municipal authority, and nothing here should be relied on operationally.
