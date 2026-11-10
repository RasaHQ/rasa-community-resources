# Frameworks with Rasa

Keep the worker, graph or media pipeline your team already owns, and give users
a Rasa conversation around it. This directory contains public tutorial code,
not internal framework rankings or benchmark results.

## LangGraph statement handoff

The current worked example uses fictional Jacaranda Bank. `langgraph/` is an
independent graph: it reads synthetic statement rows, pauses to ask a month and
totals travel spending. Its SQLite checkpoint survives separate worker processes.
`langgraph-mantle/` is the separate Rasa conversation. `statement-handoff/` binds
the conversation's selected demo identity and current run to the worker.

Run IDs belong to the application; they are not arguments the model may invent.
The negative controls show a failed resume under a new thread and a wrong-owner
resume. A controlled owner-check mutation exists only in the native test suite,
not as an executable service mode.

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/langgraph --owner statement-demo
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/langgraph-mantle --owner statement-conversation
```

Do not create environments for every planned framework. Each selected runtime
has its own manifest and lockfile. The worker needs no API key or Rasa licence.

Run the actual workflow without a model or conversation server:

```sh
mkdir -m 700 statement-demo-state
python3 tutorials/frameworks-with-rasa/demo_statement.py \
  --worker-python tutorials/frameworks-with-rasa/langgraph/.venv/bin/python \
  --state-dir statement-demo-state --month 2026-10
```

Use a new seat-owned state directory; if it already exists, inspect it instead
of overwriting or deleting it. The replay resolves its real path. For demo A,
the expected report is 3200 pence GBP with rows S-102 and S-103. This is a direct
application/worker replay, not a model-driven transcript. Do not interpret it
as speech accuracy or banking authentication.

For the text conversation, follow `langgraph-mantle/README.md` and set
`STATEMENT_WORKER_PYTHON` and `STATEMENT_STATE_DIR` before starting Rasa. Rasa
asks the user for the public demo code and the missing month. The graph stays
responsible for its checkpoint and calculation. Restarting Rasa loses the
in-process identity/run mapping; reconnecting it safely needs an application
store and trusted identity design.

Check both sides independently:

```sh
tutorials/frameworks-with-rasa/langgraph/.venv/bin/python -B -m unittest discover \
  -s tutorials/frameworks-with-rasa/langgraph/tests -p test_checkpoint.py -v
STATEMENT_TEST_WORKER_PYTHON="$PWD/tutorials/frameworks-with-rasa/langgraph/.venv/bin/python" \
  tutorials/frameworks-with-rasa/langgraph-mantle/.venv/bin/python -B -m unittest discover \
  -s tutorials/frameworks-with-rasa/langgraph/tests -p 'test_*binding.py' -v
STATEMENT_TEST_WORKER_PYTHON="$PWD/tutorials/frameworks-with-rasa/langgraph/.venv/bin/python" \
  tutorials/frameworks-with-rasa/langgraph-mantle/.venv/bin/python -B -m unittest discover \
  -s tutorials/frameworks-with-rasa/langgraph/tests -p test_handoff.py -v
```

The native binding suite includes a real worker call. Synthetic result mutations
are labelled separately in the tests. No provider credentials are forwarded
to the worker. There are no real customers, connected account services,
financial decisions or production security guarantees.

After stopping all selected demo jobs and preserving needed evidence:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/langgraph --owner statement-demo --inactive
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/langgraph-mantle --owner statement-conversation --inactive
```

Checkpoints are separate data; environment retirement does not remove them.
Do not remove a database just because it is ignored or looks temporary.
