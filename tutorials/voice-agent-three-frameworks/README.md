# Cedar Clinic voice-agent tutorials

Build the same fictional prescription-refill assistant with Rasa Pro Mantle,
LangGraph, Strands Agents, LangChain without LangGraph, Agno, CrewAI, Pipecat
or LiveKit Agents. Cedar Clinic, its patients and their records are invented.

The agent verifies the caller, selects a medicine from their record, reads
back the proposed request and asks for confirmation before sending it to the
prescribing team. The shared clinic tools enforce identity and selection.

Rasa declares tool prerequisites and confirmation in the skill configuration,
with protected memory written by tools. The other examples use their SDK's
agent, graph, intervention, pipeline or session APIs and an application guard.
Pipecat and LiveKit also support native voice integrations; these examples
use the shared browser transport to keep the tutorial inputs consistent.

## Choose one implementation

| Directory | Runtime |
| --- | --- |
| `rasa/` | Rasa Pro Mantle; requires a Rasa Pro licence |
| `langgraph/` | LangGraph agent and state graph |
| `strands/` | Strands Agents and intervention handlers |
| `langchain/` | LangChain Core and OpenAI; no LangGraph dependency |
| `agno/` | Agno Agent and native confirmation requirements |
| `crewai/` | CrewAI Agent with a confirmation bridge |
| `pipecat/` | Pipecat pipeline and Responses service |
| `livekit/` | LiveKit Agents session and Responses plugin |

Each project has a pinned dependency lock and its own isolated environment.
Install only the selected project, following its README. Keep credential
values in a local `.env`; the committed `.env.example` lists variable names.
The five additions use community open-source SDKs. The Rasa baseline uses
Rasa Pro Mantle, as specified for this tutorial.

## Shared source and local checks

- `shared/clinic/`: fictional records, tool schemas, policy and audit functions.
- `shared/speech/` and `shared/speech-deepgram/`: speech clients.
- `shared/web/`: browser page and WebSocket protocol.
- `shared/spec/`: scripted fictional caller inputs, local checks and runners.
- `variants/`: alternate Rasa speech configurations.

Run `make test` for offline shared checks. From a selected framework folder,
run its `make test`, then `make run` and `make web` to try the assistant.
Provider calls require credentials and incur charges. For scripted local
reproduction, set an explicit output folder:

```sh
python3 shared/spec/run_spec.py rasa --label my-run --results-root /path/to/private/local-output --budget-usd 4
```

Generated results, logs and spending records stay local and are excluded from
this public source repository. Keep them when retiring an experiment; retire
only its unused environment through `scripts/workspace.py`. See
[`../../docs/WORKSPACES.md`](../../docs/WORKSPACES.md) for ownership and rebuild
instructions.
