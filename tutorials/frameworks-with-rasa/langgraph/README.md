# Keep a LangGraph statement search behind Rasa

This worker demonstrates an existing read-only workflow for fictional Jacaranda
Bank. LangGraph owns the row lookup, pause, checkpoint and total. Rasa's separate
conversation runtime will collect the missing month and resume that run.

The rows are synthetic. Neither a sender ID nor `demo_owner` authenticates a
customer. There are no bank connections, decisions, payments or model calls
in the worker. SQLite is a local development store, not a production deployment.

## Run the native checkpoint controls

From the repository root, create only this selected environment:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/langgraph --owner statement-demo
tutorials/frameworks-with-rasa/langgraph/.venv/bin/python -m unittest discover -s tutorials/frameworks-with-rasa/langgraph/tests -v
```

Tests use the actual LangGraph graph and SQLite saver, including separate worker
processes. They check that the first read is retained, incorrect input leaves
the pause intact, another demo owner cannot resume a run and a newly invented
thread cannot resume the old one. No provider key is needed. The worker pins
LangGraph 1.2.12 and SQLite checkpoint 3.1.1; `uv.lock` pins transitive packages.

Only the conversation service should choose `run_id` and `demo_owner`. The
model-facing Rasa tool must not accept them as arguments. A real service needs
trusted account identity, authorised data retrieval, retention and deletion,
database backups and concurrency planning before replacing these fixtures.

After stopping the demo and preserving any needed checkpoint database:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/langgraph --owner statement-demo --inactive
```

Retirement removes only the managed environment. It does not delete a checkpoint
database, source, manifest or evidence.
