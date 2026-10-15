# List a Rasa agent’s tools and check for changes

Author: Rod Rivera
Assessed on: 2026-10-15
Assessed by: Rasa Community
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience: Engineers reviewing the tools exposed by a trusted Mantle project
Time: 30–45 minutes

When you add a tool to an agent, the list your team reviewed can fall behind.
In this exercise, you will generate that list from Mantle’s Python tool loader,
save a reviewed snapshot and make a check fail when that list changes.
You will also inspect confirmation settings for a tool reached through
skill prose and through an ordered block.

The example uses an invented review record. Its tools return fixed local
values. They do not update a business system, send messages or make payments.
You need Python and command-line experience. You do not need a model API key
or a conversation to run the inventory exercise. The required integrations
file contains an unused loopback model route. No model service is supplied;
this resource is not a chat demo.

## What you will learn

Follow the loaded bindings, compare model and engine gate lookups, reject an
unreviewed tool change, then choose what needs extra coverage in your own
project. The example stops before conversation testing.

## Before you start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use
Python 3.12. Rasa Pro has its own licence terms; this teaching code uses the
repository’s [Apache 2.0 licence](../../LICENSE).

If you do not have a checkout, obtain the resource first:

```sh
git clone --filter=blob:none --sparse https://github.com/RasaHQ/rasa-community-resources.git rasa-resources
cd rasa-resources
git sparse-checkout set tutorials/agent-tool-inventory
```

From the repository root, enter this directory:

```sh
cd tutorials/agent-tool-inventory
make install
```

The install uses the committed lock. If installation fails, check your Python
version and package-index access before changing dependencies. Install this
resource only; do not copy another project’s virtual environment.

**Only load projects you trust.** Mantle imports their Python modules to find
tools. The `--trusted-python` flag acknowledges that code execution; it does
not make an untrusted upload safe. An import can run arbitrary Python before
any tool is called.

## Generate the tool list

```sh
make snapshot
```

The command writes JSON to standard output and SDK diagnostics to standard
error. In this supplied project, look for two tool names:

| Tool | Where its function lives | How Mantle finds it |
| --- | --- | --- |
| `record_review` | `tools/reviews.py` | The skill imports it explicitly. |
| `read_status` | `skills/review_record/tools.py` | It is local to the skill. |

The shared module also defines `unused_shared`. It should not appear: the
skill does not import it. A file search would find that function, but it would
not tell you whether this skill loads it.

Each row names the skill, target, tool, source file and source-file hash.
The same tool can have several rows because the target changes how its gates
are resolved. Paths in the JSON are relative to the inspected project.
A source-file hash changes when any part of that file changes, including
comments. This intentionally asks you to review those changes too. It does not hash
every imported helper, dependency, skill instruction or ordered-block step.
Keep normal source review and dependency checks alongside this comparison.

## Read the confirmation columns

Open `skills/review_record/skill.md`. The skill enables confirmation for
`record_review` and has an inline ordered block that executes that tool.
The inventory records two different questions:

| Column | Question it answers |
| --- | --- |
| `modelVisibleInEmptyMemory` | Does the model-facing tool selection include this binding for this target with empty memory? |
| `modelConfirmationSetting` | Is confirmation enabled in the target’s model-facing gate list? |
| `engineConfirmationSetting` | Is confirmation enabled in the engine’s effective gate lookup for this tool and target? |

For `record_review` inside `review_record__finish_review`, the supplied
fixture resolves the model confirmation setting to false and the engine
setting to true. The inline block follows a different lookup path from prose.
Do not replace those columns with one “safe” or “authorised” label.

These are resolved settings, not a recording of a person confirming an
action. To prove that a deployed agent pauses and resumes correctly, you
still need a test through its actual dispatcher and conversation path.

## Check a reviewed snapshot

```sh
make check
```

The supplied `inventory.json` is the expected snapshot for this example.
A match exits successfully and prints a JSON result with `status: match`.
The comparison includes tool bindings, targets, source hashes and gate
settings. An unresolved imported tool is refused rather than saved as a
successful inventory.

Now open `skills/review_record/tools.py` and add this tool below `read_status`:

```python
@tool(description="Read an invented revision.")
async def read_revision(context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"revision": 1})
```

Run `make check` again. It should exit unsuccessfully and report that the
inventory differs from its reviewed snapshot. The new tool and changed
source hash both need review. Remove the added function, restore the original
file contents, and repeat the check to recover the passing result.

For an intentional change, save a candidate and inspect the differences:

```sh
uv run --locked python inventory_cli.py snapshot . --trusted-python > candidate.json
diff -u inventory.json candidate.json
```

The CLI writes JSON to the candidate file and diagnostics to standard error.
`diff` exits with status 1 when it finds differences; this is the expected
result after adding a tool. The inventory check reports a refusal reason,
not a line-by-line diff. Review the candidate before replacing the approved
file. Do not regenerate it automatically in the same CI step that
compares it: that would approve every change before checking it. Keep the
previous snapshot until the new command exits successfully and its JSON has
been reviewed.

## Run the checks

```sh
make test
```

The tests exercise snapshot comparison, malformed inputs and the refusal of
unsupported scope. State-dependent skill or block gates, conditional routing,
bundled engine skills and MCP imports require more context than this example
collects. The command refuses them before loading Python tools instead of
producing a list that looks complete.

The scope tests supply native compiled skill objects. They check the
inventory’s refusal logic, not every possible Markdown spelling. The CLI
tests load the actual supplied project. Neither group runs an LLM turn.

## Apply it to your project

Run the command from this directory, naming another trusted project:

```sh
uv run --locked python inventory_cli.py snapshot /path/to/trusted-project --trusted-python
uv run --locked python inventory_cli.py check /path/to/trusted-project --expected /path/to/reviewed-inventory.json --trusted-python
```

Use the reviewed application revision and the same pinned Rasa version.
If the command refuses your project, keep the refusal in the review and add
an adapter or explicit state coverage before relying on a complete list.
Removing the refusal to get a green check loses that boundary.

The list covers custom Python bindings from the project. Built-in engine
tools are not included. This inventory is one input to a tool-access review. It does not describe
permissions inside a tool’s implementation, external service credentials,
all possible runtime states or regulatory compliance. Review those separately.
No latency, cost or model-quality comparison is made here.
