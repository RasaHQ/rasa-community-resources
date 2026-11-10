# Rasa conversation for an existing LangGraph statement workflow

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-frameworks-with-rasa-langgraph-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make train && make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** training finishes, then the server starts on port 5005.
<!-- codespaces:end -->

The worker in `../langgraph` retains its graph, SQLite checkpoints and pause.
This separate runtime collects a public demo code and a missing month through
Mantle tools. The model never chooses the worker run ID or account context.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native tool tests, project validation, licensed training and cold archive load
**Verified with:** Rasa Pro 3.21.0.dev5 native tool bindings and a real separately locked worker; no model conversation or audio qualification

Install only the selected worker and this conversation environment, separately.
Use `scripts/workspace.py start` from the repository root; keep both lockfiles.
Set the variables in `.env.example` in your terminal without committing them.
Create `STATEMENT_STATE_DIR` yourself with owner-only permissions. Use an
absolute real path (macOS `/tmp` may be a symlink; resolve your path first).

This is an in-process, localhost development example. Rasa conversation state
is not durable across restart. Worker checkpoints are durable across worker
processes, but not a complete application recovery design: reconnecting the
conversation to an old run needs a durable, authorised identity/run mapping.
SQLite contains synthetic rows only. Do not expose these tools as real banking.

```sh
cd tutorials/frameworks-with-rasa/langgraph-mantle
make validate
make train
make run
```

REST/model-driven acceptance and any optional audio channel are separate checks.
The supplied channel is text only. Test speech behavior and production
compatibility through the real channel before adding users.
