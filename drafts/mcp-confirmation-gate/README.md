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
```

This control checks an actual MCP session's description and structured result.
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

Next: wire identical gated and ungated skills into the full runtime and add an
optional paired model trial. Preserve
all outcomes, including a model that never asks for the recording tool. A gate
requires confirmation; it does not establish that the caller's consent is
informed, or that the whole application resists prompt injection.

The mock is inspired by the description/result channel distinction in
[Measuring and Exploiting Implicit Trust in LLM Tool-Calling Pipelines](https://arxiv.org/abs/2609.18217).
It is not a reproduction of that paper's attacks or reported success rates.

Keep environments, credentials and trial traces out of this source directory.
No publication or new ready-to-merge PR is requested by this draft.
