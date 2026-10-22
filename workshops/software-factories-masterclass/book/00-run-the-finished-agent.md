# Chapter 0: Run the agent you will learn to build

**Goal:** ask about a journey in ordinary words and see its flight, weather, meeting timeline and currency cards.

**You need first:** a Git clone of this repository, Python 3.12, [uv](https://docs.astral.sh/uv/), Make, a browser and internet access for installation and public source data. You also need an issued [free Rasa Developer Edition licence](https://rasa.com/rasa-pro-developer-edition-license-key-request). Submitting the sign-up form alone is not a licence. Start with text; a paid model key and voice key are optional.

The later Python-product factory exercises require a Mac with `sandbox-exec`. If you use another platform, you can read along and pair with a Mac user for those exercises. This chapter's checkpoint has not been qualified on every operating system.

## What you are looking at

**Rasa Mantle** runs the conversation: the instructions, the tool requests and the answers. A **tool** is a function the agent can ask to run. This agent's briefing tool reads public sources and produces four cards:

| Card | What it tells you |
|---|---|
| Flight | The observed aircraft position and a computed landing estimate |
| Weather | The forecast around the estimated arrival time |
| Timeline | Whether the estimated arrival and assumed travel time fit your meeting |
| Currency | Daily exchange reference rates and changes from the previous reference day |

The values come from source readers, not text invented by a model. A missing source produces an unavailable card with a reason. That is honest behaviour, but it is not the complete four-card result you are aiming for.

## Open the complete checkpoint

1. Clone the repository if you have not already:

   ```bash
   git clone https://github.com/RasaHQ/rasa-community-resources.git
   ```

   If you already have the clone, use it rather than creating a second folder. Keep this checkpoint inside the clone: the credential checks need Git metadata, so a ZIP download or an isolated copy is not supported.

2. Set the clone's actual location and enter the provided chapter code:

   ```bash
   export REPO=~/rasa-community-resources
   cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00/demo"
   make help
   make setup
   ```

   `make help` lists the commands in order. Setup installs the two locked Python 3.12 environments. It does not read or pass participant keys to package build tools. The first download takes time; later setup runs reuse the local cache.

3. Create your private credential template:

   ```bash
   make env
   ```

   Open `.env` in your text editor from the current `demo` folder. Put your issued licence after `RASA_LICENSE=`. Leave the other entries empty for the first text run. Save the file. Never paste key values into chat, a URL, a task file or a terminal command. `make env` refuses to overwrite an existing file and keeps it private. Do not commit it.

4. Check readiness:

   ```bash
   make doctor
   ```

   You should see credential **names** marked SET or MISSING, never their values. For the first run, `RASA_LICENSE` must be SET; missing model and voice keys are expected. Follow any prerequisite error before continuing. Readiness does not prove that a flight is currently available from its source.

## See how it works

1. Start the provided agent in explicitly scripted text mode:

   ```bash
   make run-scripted
   ```

   Open [the local agent page](http://127.0.0.1:8942/) after the terminal reports ready. The conversation uses the real Mantle Inspector, with the cards beside it. Keep the terminal running. A port conflict stops this checkout; it does not kill another process.

   **SCRIPTED means the tool choices are supplied by teaching code.** The engine, tool calls and public source reads are real; no model reasoning or paid model call is being demonstrated. The public sources still need internet access. The licence remains required.

2. Ask in the conversation:

   ```text
   I'm heading to New York. Which flights are already in the air?
   ```

   Choose one of the flights the source actually returns, such as “the second one”. Do not assume a sample flight number is airborne now. This checkpoint searches a bounded set of published New York routes; it is not a complete airline schedule service. If nothing matches, read the explanation and supply a flight number you know is currently airborne.

3. When asked about your meeting, answer in ordinary words:

   ```text
   The 6 pm meeting tomorrow.
   ```

   The agent uses the destination's local time. Read the airport-to-city allowance on the timeline: it is a planning assumption, not live traffic or a guarantee about immigration or baggage. Check the dates and attribution under the cards. A landing estimate is computed from position and speed, not an airline arrival promise.

## Now change it

Ask the running agent to revise the journey; do not edit its code:

```text
Allow an hour to get into town.
```

The flight and meeting should remain the same while the transfer allowance and timeline update. This is a change to the briefing through the agent's tool workflow. Later chapters use the factory to change the software itself.

## You are done when

Leave the demo running. In a **second terminal**, set the clone location again and run:

```bash
export REPO=~/rasa-community-resources
cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00"
python3 check_demo.py
```

It must exit 0 and print `ch00 OK`. The check reads the actual local HTTP card page and requires each of the four cards to be available. An empty board, three-card replay, duplicate card or unavailable card cannot pass. Also confirm in the browser that your transfer revision preserved your chosen flight and meeting. This completion check does not certify voice, model reasoning or another browser session.

Stop your own demo with Ctrl-C in its launcher terminal, or run `make stop` from that checkpoint's `demo` folder. Do not close someone else's server to free a port.

## Optional: use a model or voice

After the text path works, stop the demo. Add your own matching model key to the same ignored `.env` and use `make run`. The selected model group is in `project/integrations.yml`; a key for another provider does not make that group ready. Model sessions can incur charges; inspect your provider's account limits and usage. No per-session money cap is promised here.

For voice, also supply your own `DEEPGRAM_API_KEY`. Without it, text stays available. If voice startup fails, the launcher attempts the real Inspector once in text mode and says so. Seeing text cards is not proof that a spoken interaction worked: check the microphone and the spoken result separately.

## If it fails

- **Licence missing or refused:** use the issued Developer Edition licence, not the sign-up confirmation. Do not share its value in a support report.
- **Nothing is airborne on the supported routes:** try a source-backed active flight later. Do not invent a result or call an unavailable card complete.
- **A source is unavailable:** read its reason in the card. The completion check remains NOT DONE until all four useful cards are present; source availability is not guaranteed.
- **A port is occupied:** stop your own earlier checkpoint with `make stop`. The launcher will not stop another checkout.
- **Unsafe or tracked `.env`:** keep only the four template names, one assignment each, in a regular ignored file. `chmod 600 .env` repairs its permissions. Never force tracked credentials past the check.
- **You need to report a failure:** share the fixed error sentence, Python version and which command failed. Do not share your `.env`, headers or private briefing identifiers.

Next, chapter 1 explains the Mantle instructions and tools that made this conversation possible.
