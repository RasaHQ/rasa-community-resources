# Chapter 0: Run the agent you will learn to build

**Goal:** see four recorded source cards, then ask the actual agent to change its airport-to-city allowance without editing code.

**You need first:** a Git clone of this repository, Python 3.12, [uv](https://docs.astral.sh/uv/), Make, a browser and an issued [free Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). Submitting the form alone is not a license. Installation needs internet access. After installation, this chapter's core exercise uses recorded data and needs no live source, model key or voice key.

The Python-product factory exercises later in the book require a Mac with `sandbox-exec`. Pair with a Mac user for those checks if needed. This chapter is qualified on macOS/Python 3.12; other operating systems have not been qualified.

## What you are looking at

**Rasa Mantle** runs the conversation: instructions, tool requests and answers. A **tool** is a function the agent can ask to run. This agent's briefing tool produces four cards:

| Card | What it tells you |
|---|---|
| Flight | Aircraft position and a computed landing estimate |
| Weather | The forecast around the estimated arrival |
| Timeline | Whether arrival and an assumed transfer fit the meeting |
| Currency | Daily reference rates and their changes |

In this exercise, the position, forecast and reference rates were recorded on **22 October 2026** through the same briefing workflow. The timeline is computed from those observations and the meeting and transfer you state. Every card says **REPLAY**. These are historical observations, not current flight information. The exercise clock is fixed to the recording's day: “tomorrow” means 23 October 2026.

**SCRIPTED** means teaching code selects the tools. The Mantle engine, Inspector, tool workflow, checks and Core card renderer are real. No model reasoning is being demonstrated. The recorded adapter never opens a source or model connection.

## Open the complete checkpoint

1. Clone the repository if needed:

   ```bash
   git clone https://github.com/RasaHQ/rasa-community-resources.git
   ```

   Use your existing clone if you have one. Keep this checkpoint inside Git: credential tracking and ignore checks do not support ZIP downloads or an isolated copy.

2. Set your clone's actual location and install the supplied code:

   ```bash
   export REPO=~/rasa-community-resources
   cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00/demo"
   make help
   make setup
   make env
   ```

   Setup installs two locked Python 3.12 environments without passing participant keys to package build tools. `make env` creates a private `.env` only if absent; it never overwrites earlier values.

3. Open `.env` in your editor. Put your issued license after `RASA_LICENSE=` and leave model and voice entries empty for this exercise. Never paste a credential into chat, URLs, task files or a terminal command. Do not commit `.env`.

   ```bash
   make doctor
   ```

   You should see credential **names** marked SET or MISSING, never values, and `Readiness check passed.` A present license still must be accepted when the real engine starts. Missing model and voice keys are expected. Fix a prerequisite error before continuing.

## See how it works

1. Start the **recorded** sources through the normal agent launcher:

   ```bash
   BRIEFING_RECORDED=1 make run-scripted
   ```

   The terminal explicitly says `recorded sources (REPLAY)`. Keep it running. Open [the local agent page](http://127.0.0.1:8942/) after it reports ready. This is the actual Mantle Inspector beside Core's cards, not a replacement chat or a separately drawn page.

2. Use the flight included in the recording:

   ```text
   United 1162 to EWR
   ```

   When asked for your meeting, answer:

   ```text
   The 6 pm meeting tomorrow.
   ```

   Four REPLAY cards appear. Read their provenance and recorded times. The initial Newark-to-city allowance is **90 minutes**: a planning assumption, not traffic or a guarantee about immigration or baggage. The recording is fixed; it cannot discover today's flights.

3. In a second terminal, check the result before making your change:

   ```bash
   export REPO=~/rasa-community-resources
   cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00"
   python3 check_demo.py --recorded --transfer-minutes 30
   ```

   This must fail with `NOT DONE`, exit 1. Four cards exist, but their 90-minute allowance does not meet your new 30-minute requirement. Before the demo is running, the command also fails because it cannot reach the page.

## Now change it

In the running conversation, ask:

```text
Allow 30 minutes to get into town.
```

The agent revises the timeline through its briefing tool. The recorded flight, weather and currency observations remain unchanged; your meeting stays the same. The new 30-minute allowance is still explicitly an assumption. You do not edit a product file or a recorded value.

You can instead explore **120 minutes** by requesting it in the conversation and using `--transfer-minutes 120` in the check. Both differ from the initial 90-minute allowance. These are requests for a planning assumption, not claims about actual travel time.

## You are done when

From the second terminal, run your chosen check again:

```bash
python3 check_demo.py --recorded --transfer-minutes 30
```

It must exit 0 and print `ch00 OK`: the actual local HTTP page contains four available REPLAY cards and the requested allowance. An empty board, duplicate, three-card replay, unavailable card, public-source mode or unchanged 90-minute timeline cannot pass. Also confirm that the displayed flight and meeting stayed the same. This does not certify voice, model reasoning, a different session or future source availability.

Stop your own demo with Ctrl-C in its launcher terminal, or `make stop` from its `demo` folder. Do not kill someone else's process to free a port.

## Optional: try current public sources

After the recorded exercise, stop it. Run without the recorded flag:

```bash
make run-scripted
```

This still makes no paid model request, but the source readers now need internet access. Ask “I'm heading to New York. Which flights are already in the air?”, choose an actually returned flight, then state your meeting and transfer allowance. Discovery covers selected published New York routes, not a complete airline schedule service. If none matches, supply a flight you know is airborne; do not assume the recorded flight is airborne now.

Live observations, forecasts, computed estimates and daily reference rates have different labels. Missing sources show unavailable reasons, never invented values. `python3 check_demo.py` without `--recorded` checks four available cards for this extra. Public source availability is not required to finish the recorded core exercise.

For model reasoning or voice demonstrations, use the facilitator's separately reviewed plan with a named model, execution bounds, an expected cost range and recorded usage. The recorded exercise supplies no paid-run command. Text cards alone do not establish that a spoken interaction worked. The recorded worker refuses model-enabled mode.

## If it fails

- **License missing or refused:** use the issued license, not the sign-up confirmation. Do not share its value in a support report.
- **The check still says NOT DONE:** read the four cards. Each must say REPLAY, and the timeline must show your requested 30 or 120 minutes. Make the request through the conversation.
- **A port is occupied:** stop your own earlier checkpoint with `make stop`. The launcher does not stop another checkout.
- **Unsafe or tracked `.env`:** keep only the four template names, one assignment each, in a regular ignored file. `chmod 600 .env` repairs permissions. Never force tracked credentials past the check.
- **A live source is unavailable:** return to the recorded exercise rather than calling an unavailable card complete.
- **You need help:** share the fixed error sentence, Python version and command. Never share `.env`, headers or private briefing identifiers.

Next, chapter 1 explains the Mantle instructions and tools that made this conversation possible.
