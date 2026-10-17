# An OpenAI agent behind an MCP server that a Mantle project calls

Work in progress. Nothing here has run against a model, a licence or the network.

A Mantle skill imports `mcp/reviewer:ask_reviewer`. The server behind it (`server/reviewer_server.py`) is where an OpenAI agent would answer. The reviewer's answer is advice. The write that follows (`block_card`) is gated by Mantle's own `requires_confirmation`, and the factory's protected suite is what checks that the gate survives a change.

## What is here

| Path | What it is |
|---|---|
| `server/reviewer_server.py` | Streamable-HTTP MCP server on `127.0.0.1:8941/mcp`, one tool. The default backend is a deterministic **stub** (every result says `backend: stub`). `REVIEWER_BACKEND=openai-agents` selects the Agents SDK path, which has **not been run**. |
| `project/` | A Mantle project: `integrations.yml` declares the server under `mcp_servers`, `skills/review_dispute/skill.md` imports its tool and gates `block_card`. |
| `check_engine.py` | Engine validation and compiled gates for one project. |
| `experiments.py` | Eight variants of `skill.md` checked by the real compiler. |
| `client_probe.py` | Lists and calls the stub server over a real MCP session. |
| `RESULTS-offline.md` | What the above produced, and what it does not show. |

## Run it (no licence, no key, no network beyond loopback)

Use the pack's pinned environment (`factory/uv.lock`: `rasa-pro` 3.21.0.dev5, `mcp` 1.28.1, `openai-agents` 0.13.6). From this folder:

```bash
python -I experiments.py project
python -I check_engine.py project
python server/reviewer_server.py &      # then, in another shell
python -I client_probe.py
```

## The protected suite

`acceptance/a4_review_dispute.py` grades the compiled project (it needs `accept_lib.py` from `../factory` on `PYTHONPATH`, and `MANTLE_PROJECT` set to the project). `python grade_variants.py project` runs it on the project and on six edits of `skill.md`:

| Variant | Decision | Failing check |
|---|---|---|
| baseline | ACCEPT | none |
| gate `enabled: false` | REJECT | blocking waits for confirmation |
| gate key omitted | REJECT | blocking waits for confirmation |
| gate constraint deleted | REJECT | blocking waits for confirmation |
| the reviewer tool given the gate | REJECT | the reviewer's answer is not a confirmation |
| typo in the MCP server id | REJECT | engine findings; tool imported from a configured server |
| the "advice, never permission" line removed | REJECT | the instructions say the answer is advice |

The suite was written **after** these variants were known, so it catches them and no others, and it checks the compiled configuration and the skill text only: it makes no model call and says nothing about how the agent behaves in a conversation. Writing the suite from the task text before seeing any candidate is the procedure the pack teaches; no record shows this one followed it.

## What it shows, and what it does not

- Engine, compile time, dev5: a typo in the MCP server id and a typo in a gated tool name are each reported (one finding). A gate with `enabled: false` on the MCP tool, and the three silent removals on the local tool (`enabled: false`, the key omitted, the constraint deleted), compile to no gate with zero findings.
- Not shown: how the engine treats the gate on the MCP tool in a live conversation, behaviour under a slow or failing server, the OpenAI path, Mantle simulations, evaluation, or a production loop. Those need a Rasa licence and an OpenAI key that this work does not have.
