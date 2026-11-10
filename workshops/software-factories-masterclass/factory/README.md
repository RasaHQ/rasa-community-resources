> **Historical extension, not the current workshop entry point.** This folder retains its original prerelease fixtures and results. Start with [the participant guide](../PARTICIPANT-GUIDE.md). `openai-mcp` uses the separate Agents SDK, not the Agents API taught today. Do not upgrade these fixtures or reinterpret their recorded results as 3.21.0 results.

# mantle-factory-v1: a small software factory whose product is a Rasa Mantle agent

The factory for the Rasa Mantle masterclass in this pack. The loop is the one from the technology-neutral course "Towards Dark Software Factories" on profrod.ai: **task -> isolated change -> independent verification -> decision.** The product is a Mantle project, and the independent verification asks the real Mantle engine.

**Pinned engine:** `rasa-pro==3.21.0.dev5` (a pre-release). No model call, no Rasa license, no network after install, and none of your environment variables reach a check. Python 3.11 or 3.12.

```
uv sync --frozen
uv run python factory.py tasks/a1-block-card.json candidates/block-card-good runs/good            # ACCEPT, exit 0
uv run python factory.py tasks/a1-block-card.json candidates/block-card-gate-omitted runs/omitted # REJECT, exit 1
```

Exit status: 0 ACCEPT, 1 REJECT, 2 the factory could not run, 3 NOT_READY (this machine cannot judge anything), 4 ESCALATE (`recover.py`).

| Part | What it is |
| --- | --- |
| `product/` | The baseline: a Mantle project with an agent, a model group and no skills |
| `tasks/` | Three tasks: A1 a card-blocking skill with a confirmation gate, A2 and A3 one rule each in `agent.yml` |
| `acceptance/`, `accept_lib.py` | The protected suites and their helper, pinned by SHA-256 in each task. Write the suite from the task text before you see any candidate; the hash proves which suite ran, not when it was written |
| `candidates/` | Hand-written candidates: a good one per task, three that silently lose the confirmation gate, one that nests its rule wrongly, one that edits the acceptance suite, and two for the stale-base lesson |
| `scratch.py`, `builder/` | A working folder for a builder agent: the project, one task and instructions, nothing protected |
| `agent-runs/` | Eighteen recorded runs, nine by codex-cli 0.162.1 and nine by Claude Code 2.1.299, October 15, 2026, with decisions, patches and final messages |
| `collect.py`, `integrate.py`, `release.py`, `approve.py`, `recover.py`, `measure.py`, `stats.py`, `policy.py` | The units from the first course, adapted where the product differs |
| `environment.json`, `environment-stale.json` | What the factory requires of the machine, and a deliberately wrong version for a lesson |

## What this is not

Not a test of how Mantle behaves in a conversation. Every check reads what the engine compiles and validates from the project's files. Whether an agent then waits for the caller at run time needs a model and is a different experiment. A copied folder is not a sandbox, and `approve.py` is a stand-in for a person.
