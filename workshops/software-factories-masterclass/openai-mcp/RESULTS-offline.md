# Offline results: stub reviewer MCP server behind a Mantle skill

Offline run on 2026-10-16. rasa-pro 3.21.0.dev5, openai-agents 0.13.6, mcp 1.28.1, the environment pinned in `../factory/uv.lock`. No license, no key, no model call, loopback only. The reviewer is a deterministic STUB (every result says backend: stub). The OpenAI Agents SDK path in reviewer_server.py was NOT run.

Run: `python -I experiments.py project` (engine variants), `python -I client_probe.py` with `server/reviewer_server.py` running (MCP session).

## Engine, compile time (experiments.py; findings = collect_project_findings)

| Variant | Findings | Compiled gates |
|---|---|---|
| baseline | 0 | block_card True, ask_reviewer None |
| typo in MCP server id (mcp/reviewr:...) | 1 (skill.import_tools.invalid_shared_tool) | block_card True |
| typo in gated tool name (block_cards) | 1 (mantle.validation.tools.unresolved_tool) | block_cards True, block_card gate not compiled to the real tool |
| gate on the MCP tool, enabled true | 0 | ask_reviewer True |
| gate on the MCP tool, enabled false | 0 | ask_reviewer None |
| local gate enabled false | 0 | block_card None |
| local gate key omitted | 0 | block_card None |
| local gate deleted | 0 | block_card gone |

## MCP session (client_probe.py, stub server)

list_tools returns ask_reviewer with an outputSchema; call_tool returns structuredContent {backend, ok, reason, verdict}. Two descriptions gave looks_unauthorised and unclear, by keyword.

## Found while checking

The Agents SDK refuses an `extra="allow"` pydantic model as `output_type` (UserError: strict JSON schema). The first version of the server would have failed on its first live call. Fixed with a separate strict `Verdict` model; AgentOutputSchema(Verdict) now builds. Only the schema was checked, not a run.

## Not shown

Runtime behavior: whether the engine honors a gate on the MCP tool when a conversation runs; behavior under a slow or failing server; the OpenAI path; simulations, eval, a production loop. Those need a license and/or a key.
