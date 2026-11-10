# Give existing Strands tools a Rasa conversation

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-frameworks-with-rasa-strands-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make train && make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** training finishes, then the server starts on port 5018.
<!-- codespaces:end -->

Mantle collects the missing synthetic network area and calls a fixed read-only
Strands tool. Direct-call recording is disabled so callers' questions are not
added to the shared Strands agent history. The local Strands runtime explicitly
refuses generation; Mantle still uses its configured conversational model.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native tool tests, project validation, licensed training and cold archive load
**Verified with:** Rasa Pro 3.21.0.dev5, strands-agents 1.57.1; 18 distinct native controls; native tool dispatch, wrapper context and decorated Mantle bindings

## Run the example

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/strands-mantle --owner network-conversation-demo
cd tutorials/frameworks-with-rasa/strands-mantle
make test
make validate
```

The selected locked environment installs the worker from its local source. Tests
need no provider credentials. Set your own RASA_LICENSE for training and
OPENAI_API_KEY for an actual Mantle conversation, using .env.example as the
variable list. Never commit credentials.

```sh
make train
make run
```

The REST channel binds to 127.0.0.1:5018. In another terminal:

```sh
curl -sS http://localhost:5018/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"network-demo","message":"Why is my connection slow?"}'
curl -sS http://localhost:5018/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"network-demo","message":"Use the north demo area"}'
```

These are reader exercises, not a recorded model run. Keep the same sender for
the missing selection. Check for source JM-N-101 with revision 2026-10-11 and a
degraded area observation. A second sender selecting south should retrieve
JM-S-201, not reuse north. Check that the assistant never claims a subscription
was changed or treats an area observation as a device diagnosis.

## Boundaries and cleanup

The area selection is public, not authentication. Mapping lives in process
memory and resets on restart. Disabling direct-call history does not erase a
tool's own logs or state. The agent-as-tool controls capture model inputs under
reset and preserved context. Native bindings inspect the selected area and
returned observation.

Stop your own server, then retire from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/strands-mantle --owner network-conversation-demo --inactive
```
