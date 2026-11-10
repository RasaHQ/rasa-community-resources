# Replace the Deep Agents database chat with Mantle

This is a complete runtime replacement for this bounded read-only SQL application.
The target never invokes Deep Agents. It is not an automatic conversion of every
Deep Agents feature, nor a migration of existing conversation/checkpoint data.

## 1. Inventory the application before changing it

The source is `deepagents/agent.py` and its skill under `deepagents/workspace/skills`.
It exposes four SQL functions. The task is to read schemas, plan a query, compile
it, execute it and explain aggregate results. The source profile excludes shell
execution and its implicit general-purpose subagent. Files support skill loading;
they are not customer deliverables in this application.

If your application uses writable agent files, delegated context, persistent
checkpoints or long-running jobs, inventory those separately. This target does
not implement those requirements. Keep the current runtime until each required
capability has its own accepted replacement.

## 2. Preserve business rules, replace framework code

| Source | Target | Migration action |
| --- | --- | --- |
| `shared/database.py` | Same file | Keep read-only execution and result contract |
| `shared/instructions.txt` | `mantle/agent.yml` | Carry the task rules into the persona |
| LangChain `@tool` wrappers | `mantle/skills/query_store/tools.py` | Use async Mantle tools with ToolContext and ToolResult |
| Source skill text | `mantle/skills/query_store/skill.md` | Name native tools with `@tool` references |
| `ChatOpenAI` and `create_deep_agent` | `mantle/integrations.yml` and Mantle runtime | Configure the model; remove graph creation from the target |
| Source `.local` workspace | No target agent filesystem | No file-producing task is carried over |

Do not copy a Deep Agents virtual environment into the target. The target's
`pyproject.toml` and `uv.lock` install Rasa and the shared package, without Deep
Agents. Rasa Pro requires a licence. Keep the published dependency locks and
use the SDK version they pin; qualify upgrades separately.

## 3. Check the target before making provider requests

From the tutorial root:

```sh
make test
make audit-target
make data
cd mantle
python3 ../../../scripts/workspace.py start . --owner chinook-mantle-demo
make validate
make test
```

`make test` at the tutorial root skips native checks if Rasa is unavailable.
The same command inside `mantle` uses its locked interpreter; the cold-load test
must run, not skip. `test_target_loads_and_invokes_with_deepagents_imports_blocked`
installs an import blocker before loading the trained archive in a fresh child,
checks the blocker itself, and runs the real Mantle query invoker over a temporary
SQLite database. It does not run a model conversation.

`audit_target.py` checks selected source files and the target lock. Counter-tests
reintroduce a Deep Agents lock entry or source import and require refusal. This
is a static check, not a scanner for arbitrary dynamic imports or production
services. Keep the native cold-load check too.

## 4. Run Mantle on its own

Set `RASA_PRO_LICENSE` and `OPENAI_API_KEY` explicitly in your terminal. Do not
borrow another project's dotenv file or commit keys.

```sh
make train
make run
```

No Deep Agents process or worker is started. From a second terminal in `mantle`:

```sh
curl --fail-with-body http://localhost:5005/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"chinook-migration-1","message":"Which five billing countries generated the most revenue?"}'
```

This makes billed model requests. For the expected answer, run `python3 oracle.py`
from the tutorial root. Compare returned SQL, rows and final reply. The original
README explains how to retain native Deep Agents messages and Mantle tracker
events locally. Each runtime assembles its own model requests. Capture complete request and usage records when comparing the two.

## 5. Accept the application, then change your client

Require the same country totals, an employee-revenue join, clarification of an
ambiguous metric, refusal of writes and a separate follow-up case. Keep fresh
and continuing conversations separate. Check application `status` as well as
runtime error flags. Save the actual outcomes; this repository does not contain
a completed model accuracy or cost comparison.

Point a separate test client at the Mantle REST endpoint first. When the accepted
cases pass, change the client route for new conversations only. Do not treat a
Deep Agents checkpoint or `.local` workspace as a Mantle tracker. Keep old
sessions on their original endpoint until they finish, or explicitly start a
new conversation; no automatic history conversion is supplied.

## 6. Retire the old runtime and retain rollback evidence

The completed target contains `mantle/` and `shared/`, plus the verified public
database and its dependency locks. It does not need `deepagents/` installed or
running. A model archive alone is insufficient: the external shared package
must also be installed. Keep the complete source revision for rollback.

If you already followed the README source comparison, its environment is registered; reuse it. Otherwise, register the source environment once, before its first use, from the repository root:

```sh
python3 scripts/workspace.py start tutorials/deepagents-to-mantle/deepagents --owner chinook-source-demo
```

The tool installs the selected lock and records that owner in the environment.
Use an unused owner name for your experiment, and use the same name when retiring it.
An existing unmanaged or differently owned environment requires an audit; the
workspace tool refuses to adopt it silently.

After the old endpoint has no continuing sessions or jobs, preserve unique
outputs and journals, then run this from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/deepagents-to-mantle/deepagents --owner chinook-source-demo --inactive
```

The target can be retired after your experiment with the same command using
`mantle` and its recorded `chinook-mantle-demo` owner. Keep its source and locks.
Do not remove another owner's
environment or delete files just because they are ignored. Rollback changes the
client route for new sessions back to the retained source release; it does not
merge conversation histories. Do not change real traffic as part of this demo.
