# Give an existing CrewAI research crew a Rasa conversation

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-frameworks-with-rasa-crewai-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make train && make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** training finishes, then the server starts on port 5019.
<!-- codespaces:end -->

Mantle collects a public synthetic HarborCover claim type and explains a checked
checklist. CrewAI keeps its source researcher, checklist writer, registered tool
and configured model. The application checks both structured tasks and recorded
tool failures before returning research to the conversation.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native task-record controls, decorated Mantle bindings and licensed build qualification
**Verified with:** Rasa Pro 3.21.0.dev5, CrewAI 1.15.27 and Python 3.12.13; 36 native controls, project validation, licensed training and cold archive load passed
**Industry:** General
**You learn:** How to give an existing CrewAI research crew a Rasa conversation that checks its results.
**Catalog name:** CrewAI research crew with a Rasa conversation

## Start both selected runtimes

The pinned releases require different PyJWT versions. Keep their separate locks
and connect them through the small standard-library JSON bridge. The bridge
starts a fixed worker process for each question; there is no worker server to
install or keep running.

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/crewai --owner claim-crew-demo
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/crewai-mantle --owner claim-conversation-demo
cd tutorials/frameworks-with-rasa/crewai-mantle
make test
make validate
```

The native controls run the actual Crew executor with scripted model responses.
They inspect completed tasks, tool failures, the process handoff and decorated
Mantle bindings. For a live conversation, export `RASA_PRO_LICENSE` and
`OPENAI_API_KEY` using `.env.example` as the variable list. `CREW_MODEL` selects
the crew's model; Mantle's model is configured separately in `integrations.yml`.
Each retained model makes its own provider requests.

`CREW_WORKER_PYTHON` can select an existing compatible crew interpreter. The
example defaults to the sibling CrewAI project's managed environment. Keep that
setting under application control; customer input is sent as JSON on stdin.

```sh
make train
make run
```

The REST channel binds to `127.0.0.1:5019`. In another terminal:

```sh
curl -sS http://localhost:5019/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"claim-demo","message":"What documents do I need?"}'
curl -sS http://localhost:5019/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"claim-demo","message":"Use the vehicle example"}'
```

For this reader exercise, keep the same sender when supplying the missing claim
type. Check for source `HC-V-101`, revision `2026-10-11`, Incident details and
Repair estimate. A second sender choosing travel should get `HC-T-201` and its
travel documents. Test a source failure too: the assistant should explain that
research is incomplete and offer a retry or stop.

## Runtime boundaries

The corpus and choices are public and synthetic. The exposed tools select a
claim type and research its required documents. The sender mapping is process
memory and resets on restart.

<!-- editor-security-note: A REST sender identifier requires separate customer authentication. -->
The example's sender mapping does not authenticate a customer. Add your
identity and access controls before connecting private claim records.

The process handoff accepts the expected public source, revision and exact
checklist. Worker failures, malformed output and a timeout become incomplete
results. The child process has a 25-second timeout, inside the Mantle tool's
30-second allowance. Cancellation of the awaiting conversation can leave its
worker running until that subprocess timeout; account for those lifetimes in
service shutdown and capacity planning.

Stop your own server and finish any worker operation, then retire both selected
environments from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/crewai-mantle --owner claim-conversation-demo --inactive
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/crewai --owner claim-crew-demo --inactive
```
