# Move a Deep Agents database chat to Mantle

Two native chat implementations install the same local read-only SQL package and
Chinook public sample database. This is a task migration, not a replacement
for every Deep Agents feature. No customer-specific data or internal results
belong here.

## Prepare the public data and check the tool boundary

```sh
cd tutorials/deepagents-to-mantle
make test
make data
```

The tests need only Python's standard library. The data download is pinned
and verified before writing. Do not point this demonstration at production
records: read-only access does not provide row-level access control or protect
personal information in free-form queries. Deploy aggregate views and enforce
your own authorisation in a real service.

## Deep Agents chat

```sh
cd deepagents
uv sync --locked --python 3.12
# Set OPENAI_API_KEY explicitly in this terminal, without saving it in Git.
uv run --locked python agent.py "Which five billing countries generated the most revenue?"
```

Each invocation creates a fresh local workspace containing only the declared skill.
Generated files remain under `deepagents/.local/` for your inspection.
The model and reasoning setting match the Mantle configuration. Deep Agents
file tools and skill loading remain enabled. This pinned harness profile does
not add a to-do middleware; the skill plans joins in prose. Shell execution and
its implicit general-purpose subagent are explicitly disabled for this
single-agent task. This is an adapted profile, not the upstream default.

## Mantle chat

Rasa Pro requires a licence. Set `RASA_PRO_LICENSE` and `OPENAI_API_KEY` in
your terminal according to the Rasa installation documentation.

```sh
cd ../mantle
uv sync --locked --python 3.12
uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))"
uv run --locked rasa train
uv run --locked rasa run --enable-api --port 5005
```

In a second terminal:

```sh
curl --fail-with-body http://localhost:5005/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"chinook-demo-1","message":"Which five billing countries generated the most revenue?"}'
```

Use a new sender for an independent session. Follow-up questions should reuse
the sender. Provider calls are billed. No paid run starts with `make test`.

## What changed from the upstream example

The upstream SQLDatabaseToolkit checker calls another LLM; our shared checker
only compiles SQL. The upstream example uses Claude and a SQLAlchemy connection;
these builds use the same GPT model and a SQLite authorizer. Neither modification
is evidence that Mantle is cheaper. Comparing costs requires capturing every
native model request in both implementations, including hidden helpers and
retries. The system prompt bytes differ after each runtime adds its instructions.

Both builds share task instructions, schemas and query results; the frameworks
add different prompts. Mantle's skill references use `@tool`; Deep Agents reads
its skill file. Mantle does not acquire the Deep Agents filesystem or optional planning
API simply because its tools answer the same database questions. Background
jobs, delegated agents, shell execution, persistence across restarts and A2A
are outside this example. Do not call tool composition subprocess isolation.

## Troubleshooting

- Missing database: run `make data` in the tutorial root.
- Checksum mismatch: keep the existing file and investigate its origin.
- Unknown table or column: list tables and inspect the schema before retrying.
- Too many rows: add an explicit limit or narrower filter; results are not silently truncated.
- Missing model key or Rasa licence: configure it explicitly in the terminal.
- Generic tool error: verify the async Mantle binding and native tool invocation;
  a direct library test does not qualify the engine.

Keep each lock with its project. Create only the environments you use, through
the repository workspace tool. Do not copy environments into worktrees or
backups. Retire them after the local experiment finishes; retain unique local
outputs and dependency manifests.

Both implementations use OpenAI Responses with the pinned GPT-5.5 snapshot.
Its Chat Completions endpoint rejects function tools with low reasoning; the
Deep Agents model therefore sets `use_responses_api=True` explicitly.


## Inspect SQL and compare the answer

From `deepagents`, `uv run --locked python inspect_chat.py QUESTION --out .local/chat.json`
saves the native message list, including tool calls and tool results. It refuses
an existing output path before any new model request. For the local Mantle REST
example, save its response and fetch
`/conversations/chinook-demo-1/tracker?include_events=ALL&start_session=false`
from the same local server. `tool_executed` events contain `arguments`, `result`
and `is_error`. These are your local tutorial outputs; do not commit them.
From the tutorial root, `python3 oracle.py` prints independent billing-country
revenue over the hash-checked public database. Compare the query, all returned
rows and the final answer, rather than grading a plausible sentence alone.

The cold-dependency mutation blocks new imports of the shared package with a
MetaPathFinder; it does not uninstall anything. A warm process with the package
already imported loads the archive, while a fresh process with the dependency
unavailable refuses it. The normal fresh-process test then proves loading with
the correctly installed dependency. This is offline fault injection, not a live
model or a measured production incident.

When inspecting Mantle tracker events, check the returned application `status`
as well as `is_error`. In this wrapper a refused SQL result uses
`{"status": "error", "reason": ...}`; the pinned runtime parser detects
`error`/`errors` fields, so that application refusal can have `is_error=false`.
The native write-refusal test checks this distinction.
