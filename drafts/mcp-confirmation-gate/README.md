# Test confirmation after reading an MCP tool result

Work in progress for site brief #134, `test-a-gate-against-split-mcp-payloads`.
This directory is not a qualified tutorial or a maintained catalog project.

The initial fixture exposes one tool over loopback streamable HTTP. Its tool
description supplies an operation name; its result supplies a fictional canary.
It reads no credentials and performs no forwarding or external writes.

With the pinned Rasa 3.21.0.dev5 SDK environment, run from this directory:

```bash
python -m unittest test_transport -v
python -m unittest test_native_confirmation -v
python -m unittest test_compiled_variants -v
python -m unittest test_prepared_project -v
python -m unittest test_cold_archives -v
python -m unittest test_turn_loop -v
```

This control checks an actual MCP session's description and structured result,
then binds and calls the same tool through Mantle's native MCP runtime and
shared connection pool. Its bootstrap stand-in supplies the native connection
settings and import allowlist; it is not a trained archive or a full chat turn.
It does not show that a model follows the instruction.

Six separate controls exercise the installed native confirmation gate and tool
invoker with an in-memory tracker stand-in. They check same-turn refusal,
stored arguments, single execution, cancellation, boolean validation and pending
recall. The ungated invoker control records immediately. These are isolated
component checks, rather than a full chat or an MCP-to-engine integration test.

The tests supply the resolution flag directly. A later `confirmed: true` runs
the stored tool; this does not prove that a model inferred informed consent
from the caller's words. Test that interpretation separately before claiming
that caller approval is enforced.

The skill template differs only in the confirmation flag. A separate native
compiler/catalog control checks that the imported MCP tools match and that the
confirmation constraint is active in one variant and inactive in the other.
The prepared-project control also runs native validation on both source
configurations, with a clearly fake key. It neither trains nor starts a chat.

Prepare new run directories without copying an environment:

```bash
python prepare.py --variant gated --run-dir /tmp/mcp-gated --mcp-port 8937
python prepare.py --variant ungated --run-dir /tmp/mcp-ungated --mcp-port 8937
```

Existing directories are refused rather than overwritten. Each prepared source
has file checksums in `variant.json`. Both projects use the same local mock
server address and model configuration. Only the confirmation flag differs.

The complete lock was installed into a fresh isolated environment on macOS
Arm64 with Python 3.12.13. All nine transport, native confirmation, compilation
and source-validation controls passed there. Package download caches were
retained; this was not an empty-cache download test. See `qualification.json`
for the dependency pins, input hashes and scope.

To repeat these controls from this directory:

```bash
uv sync --locked
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=1 \
  OPENAI_API_KEY=placeholder-not-a-real-key \
  uv run --locked python -m unittest discover -p 'test_*.py' -v
```

The placeholder is sufficient for source validation. These controls do not
call a model provider or qualify complete chat turns.
Use one environment for this paired experiment; preparing either variant
copies source files only.

An additional control packages both projects through the same native function
used by Mantle's `rasa train`. Each archive then loads in a fresh process from
an empty working directory, with the original source path unavailable. The
loaded catalogs retain the same MCP import and their opposite confirmation
flags. All ten controls pass. `archive-qualification.json` records the archive
hashes before the temporary test files are removed. This direct packager check
does not exercise the licensed CLI command or a complete orchestrator turn.

The paired turn-loop control now runs the archived agent through
`Agent.handle_message` and its actual MCP connection. A scripted model reads
the imported description and result, then deliberately requests a local
recording without caller approval. The gated variant records an awaiting
confirmation result; the simulated recording occurs only after a later user
turn and scripted confirmation. The ungated variant records immediately.
The real gate, invoker and tracker remain in use. All eleven controls pass;
`runtime-qualification.json` records their scope and source hashes.

The runtime needs its live `integrations.yml` in the working directory. It
must also await `agent.prepare_runtime_integrations()` after `Agent.load`
before handling MCP-dependent messages. The test supplies only that live
configuration beside the archive; the original prepared source path is
unavailable. No environment or credential file is copied.

These scripted choices do not measure whether a real model follows either
piece of the mock payload or understands the caller's words. Next: qualify
the documented CLI/HTTP chat path and, separately, any optional model trial. Preserve
all outcomes, including a model that never asks for the recording tool. A gate
requires confirmation; it does not establish that the caller's consent is
informed, or that the whole application resists prompt injection.

The mock is inspired by the description/result channel distinction in
[Measuring and Exploiting Implicit Trust in LLM Tool-Calling Pipelines](https://arxiv.org/abs/2609.18217).
It is not a reproduction of that paper's attacks or reported success rates.

Keep environments, credentials and trial traces out of this source directory.
No publication or new ready-to-merge PR is requested by this draft.

## Train the two prepared projects

Both variants also passed the licensed `rasa train` CLI on the pinned SDK.
`cli-qualification.json` records their source commit, archive hashes and
redacted log hashes. The licence was kept local; a placeholder model key was
sufficient for packaging. This check did not start a chat endpoint.

Set your Rasa Pro licence in your shell before the CLI command. For packaging,
you can use `OPENAI_API_KEY=placeholder-not-a-real-key`. From this directory,
capture the interpreter in the experiment's existing environment:

```bash
mcp_python="$(pwd)/.venv/bin/python"
```

Prepare the gated and ungated directories with the earlier commands, then run
the following from each prepared directory. Both commands should finish with
a saved model archive in that project's `models` folder:

```bash
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  "$mcp_python" -m rasa train
```

The interpreter remains in the original project. The prepared directories
contain the source configurations and generated archives, without another
Python environment. Use a real model credential only when you deliberately
run a live chat trial; the scripted controls use no such credential.
