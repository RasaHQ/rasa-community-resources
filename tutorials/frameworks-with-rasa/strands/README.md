# Reuse Strands network tools through a Rasa conversation

Keep the existing Strands Agent and read-only tool registration. This synthetic
Juniper Mobile example calls the native tool directly with history recording
explicitly disabled. Mantle collects the missing area and explains its returned
observation. The demo Strands model deliberately refuses generation.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native tools, actual Mantle bindings and licensed build qualification
**Verified with:** strands-agents 1.57.1, Python 3.12, 15 native controls plus three actual Mantle binding controls

## Run the native controls

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/strands --owner network-tools-demo
cd tutorials/frameworks-with-rasa/strands
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Inspect the same native tool with recording enabled and disabled:

```sh
.venv/bin/python demo_history.py
```

The supplied fixture prints source `JM-N-101` in both cases. Its pinned SDK
records four messages with recording enabled and zero with recording disabled.
Each case starts with a fresh agent. The fixture model refuses generation.

Direct calls record the question and result in agent history by default. The
native controls compare that path with an explicit nonrecording call. Separate
agent-as-tool controls use a scripted native Model: default context reset omits
the previous fixture question, while preserve_context=True retains it.
The controls capture native wrapper inputs alongside the calling agent’s messages.

Inspect caller messages alongside the specialist's second model input:

```sh
.venv/bin/python demo_context.py
```

The matrix crosses direct-call recording with specialist context preservation.
With preservation enabled and recording disabled, the caller stores zero
messages while the specialist's second input still includes caller A. These
synthetic caller labels intentionally share one specialist. Retain context
within its intended user/task lifetime; an empty parent history does not reset
that specialist. The replies are scripted and make no provider requests.

`NetworkSession` calls only inspect_network, validates its result and never
accepts a model-supplied tool name. A wrong-area result, extra action field or
native tool error is withheld. The fixture handler has no subscription action.
Disabling agent history does not make arbitrary existing tools stateless or
safe: inspect handlers and their own storage before reuse.

The public network areas north/south are synthetic selections, not account
identity. Session mapping is process-local. See ../strands-mantle for the Rasa
conversation; its selected environment also installs this package, so you do
not need both environments to run the decorated bindings.

When this experiment and its jobs finish, retire from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/strands --owner network-tools-demo --inactive
```
