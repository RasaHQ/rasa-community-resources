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

The dependency manifest pins the two directly exercised packages. The initial
checks reuse an owned SDK environment on those pins; a fresh install of this
draft's complete lock has not yet been qualified.

Next: qualify the dependency lock, train the prepared projects and exercise the
complete runtime in an optional paired model trial. Preserve
all outcomes, including a model that never asks for the recording tool. A gate
requires confirmation; it does not establish that the caller's consent is
informed, or that the whole application resists prompt injection.

The mock is inspired by the description/result channel distinction in
[Measuring and Exploiting Implicit Trust in LLM Tool-Calling Pipelines](https://arxiv.org/abs/2609.18217).
It is not a reproduction of that paper's attacks or reported success rates.

Keep environments, credentials and trial traces out of this source directory.
No publication or new ready-to-merge PR is requested by this draft.
