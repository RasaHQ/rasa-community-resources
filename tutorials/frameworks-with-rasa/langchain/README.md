# Reuse a LangChain policy retriever in a Rasa conversation

Keep the existing LangChain retriever and its document metadata. The Rasa tool
returns permitted source quotations for a synthetic Jacaranda Bank card policy.
A separate prompt/model pipeline remains available for an existing worker, but
the conversation handoff does not call that worker model or trust its conclusion.
No LangGraph dependency is needed.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native retrieval, citation and application handoff tests
**Verified with:** langchain-core 1.6.6, Python 3.12, 20 native controls; 5 additional decorated Mantle controls in the companion project

## Run the native controls

From the repository root, install only the selected experiment:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/langchain --owner policy-retrieval-demo
cd tutorials/frameworks-with-rasa/langchain
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

The native pipeline uses a scripted LangChain chat-model fixture. It exercises
actual retriever, prompt and model interfaces without provider credentials.
The quotation-membership control deliberately accepts a false conclusion that
carries a genuine quotation. A matching citation is not proof of entailment.

## Add the conversation

Use `../langchain-mantle` for the real decorated Rasa tools. The application
binds a public demo selector to personal or business sources; the model supplies
only the question. The toy keyword retriever illustrates this boundary, not
semantic search quality. Replace it with your existing authorised retriever
while preserving source ID, scope and revision metadata and the refusal tests.

Selectors are synthetic examples, not authentication. Scope mapping lives in
process memory and resets on restart. Before using real customer documents,
provide authorised identity, durable mapping and a data-access policy.
No tool replaces a card or performs an account action.

After this experiment and its processes finish, return to the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/langchain --owner policy-retrieval-demo --inactive
```

Keep the lockfile, source and any results needed for your next run. Native
controls do not measure provider accuracy, spoken delivery or model conversation.
