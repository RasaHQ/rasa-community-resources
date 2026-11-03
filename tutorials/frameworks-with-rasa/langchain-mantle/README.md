# Give an existing LangChain retriever a Rasa conversation

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-frameworks-with-rasa-langchain-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

The native LangChain retriever supplies source excerpts; Mantle collects the
missing public demo selector and explains the returned evidence. There is no
additional worker-model call in this tool. The separate LangChain prompt/model
pipeline is retained for teams that already have one, but its generated
conclusion is not treated as a verified source.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native tool tests, project validation, licensed training and cold archive load
**Verified with:** Rasa Pro 3.21.0.dev5, langchain-core 1.6.6; 25 distinct native controls across both projects; no model conversation or audio qualification

## Run the example

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/langchain-mantle --owner policy-conversation-demo
cd tutorials/frameworks-with-rasa/langchain-mantle
make test
make validate
```

`make test` runs the 20 core controls and five actual decorated-tool controls.
This selected environment installs the worker through its local editable source;
you do not need both environments to exercise the conversation bindings.

Set `RASA_LICENSE` and `OPENAI_API_KEY` from your own authorised credentials,
using `.env.example` as the variable list. Never commit the resulting `.env`.
Licensed training uses `RASA_LICENSE`; an actual model conversation also uses
the OpenAI key and incurs provider charges.

```sh
make train
make run
```

The localhost REST channel uses port 5017. In another terminal, exercise the
conversation with a stable sender ID:

```sh
curl -sS http://localhost:5017/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"policy-demo","message":"Can I replace a damaged card?"}'
curl -sS http://localhost:5017/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"policy-demo","message":"Use personal demo 111111"}'
```

These commands are a reader exercise, not a recorded model run. Record the
question, selected demo, retrieved source and response. Check that personal
source P-101 is cited with revision 2026-10-11 and that the response explains the policy
without reporting a completed replacement. Use a new sender with business demo 222222 to check B-201.
The application's sender ID is not proof of customer identity.

## Boundaries and cleanup

Demo scope is process-local and cannot change within a conversation; it resets
on restart. A production service needs authorised identity, durable mapping and
data-access policy. Check whether the final answer follows from its evidence, separately from
citation identity and quotation membership. There is no account-action tool in this example.
The supplied channel is text only. Test any added speech channel with its actual
providers before release.

Stop your own running server before retiring the environment from the repository
root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/langchain-mantle --owner policy-conversation-demo --inactive
```
