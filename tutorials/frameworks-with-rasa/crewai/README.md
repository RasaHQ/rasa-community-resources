# Retain a CrewAI research crew and inspect its task outputs

A source researcher and checklist writer produce a public synthetic HarborCover
claim-document checklist. This development fixture uses the native sequential
Crew executor and scripted BaseLLM responses. The controls inspect
actual task records and tool failures using scripted model responses. The tools
read public synthetic claim-document requirements.

The application inspects the two expected structured task outputs and recorded
tool failures before exposing a checklist. A finished-looking final paragraph
alone is not its acceptance contract. The WARN-policy control deliberately
returns a valid-looking final answer after the source tool reports failure.

## Run the native controls

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/crewai --owner claim-crew-controls
cd tutorials/frameworks-with-rasa/crewai
make test
```

The native suite passed 25 controls on 11 October 2026. A separate Mantle
adapter and fixed worker process are in `../crewai-mantle` and `worker.py`;
their combined qualification passed 36 distinct controls, licensed training
and a cold archive load. The native controls use scripted model responses.

When your tests finish, retire the selected environment from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/crewai --owner claim-crew-controls --inactive
```

## Compare failure signals before adding a channel

```sh
.venv/bin/python demo_failure_signals.py
```

Six native cases keep the error wording constant and vary its representation
and policy. A plain error string records zero failures under IGNORE, WARN and
RAISE, so this application's checklist guard accepts the scripted task outputs.
Declaring a ToolFailure records it under WARN and aborts under RAISE. Each case
observes the actual source tool invocation; the model replies are scripted.
Retain useful existing tool handlers, but adapt their business-failure outcomes
into the declared failure type before relying on a native failure flag.
