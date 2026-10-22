# Mantle flight-briefing project

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided — independent end-to-end acceptance pending
Verified with: maintained rasa-pro pin and registry locks; see the resource qualification checkpoint
Audience: Practitioners running the flight-briefing demo
Time: Allow time for the first dependency download

Start with the [example README](../README.md). From the **example directory**,
prepare the ignored credential template with `make env`, fill in your own values
privately, then use one setup command and one run command:

```sh
make setup
make run
```

The launcher creates separate locked worker and Mantle environments, trains the
project, starts the authenticated briefing service and the actual Inspector,
and prints the combined page address. Ctrl-C stops its own processes. Do not
start a second manual backend or supply a transport token yourself.

Both environments use registry artifacts recorded in their locks. The worker
has the OpenAI Python client for the Agents API; Mantle keeps its separate compatible OpenAI client. Their
exact Core artifact is recorded in `../worker/core-artifact.json`.

The actual Inspector requires your `RASA_LICENSE`, including in scripted mode.
Model and voice keys are optional for the explicitly labelled scripted text
path: `./demo run --scripted`. That path uses deterministic tool selection;
it is not evidence of model reasoning. `scripted_demo.py` is a separate historical
console replay harness, not the graphical demo entrypoint.

Ask in ordinary words, for example “I'm heading to New York. Which flights are
already in the air?” Choose a returned flight, then give your meeting day and
time. Code resolves supported airline/airport aliases and destination local time.
The panel distinguishes live observations, forecasts, computed estimates,
published routes and changeable travel assumptions. See the main README for
coverage and the current finder-release integration checkpoint.

Use only your own example-root ignored `.env` or process environment. Never put
credentials in chat, URLs, MCP arguments, committed files or logs. Setup and
offline tests do not require `.env`. The launcher handles runtime dotenv loading;
model selection stays in `integrations.yml`, with environment references.

The class uses capability possession: `briefing` returns a private identifier
needed by get/revise, and discovery returns one for numbered selection. Sharing
an identifier grants access. There is no claim of engine-user isolation or
enforced model memory. Presentation hooks redact identifiers without changing
tool arguments and replace unchecked model summaries with validated notices.

Source tests, SDK checks and the scripted engine/MCP harness are intermediate
evidence. Final registry finder integration, independent fresh-clone acceptance,
actual browser/voice checks and the factory second act remain separate gates;
consult the main README rather than treating a successful unit test as a class pass.
