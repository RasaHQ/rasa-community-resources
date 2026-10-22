> **22 October revision:** Start with [the participant guide](../PARTICIPANT-GUIDE.md) for the three-hour route, current API distinctions, and platform requirements. These chapters are reference exercises; their checks do not certify the complete voice-to-build-to-voice journey.

# Chapter 0: Run the agent you will learn to build

Picture a flight that lands at 5 pm, with a meeting at 6 pm across town. In about 20 minutes, after a first install, you'll run an agent that answers that from four sources at once, then change how it answers without touching its code.

Time: about 5 minutes for the first install, then about 20 minutes. You need: Python 3.12, [uv](https://docs.astral.sh/uv/), Git, Make, a browser and your free [Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). Submitting the sign-up form alone isn't a license. The install needs the internet. After that the exercise runs offline, because the cards are a recording from 22 October 2026. Chapter 0 runs on Rasa Pro 3.21.0, tested on 22 October. The standalone example in `examples/` stays on 3.21.0.dev5 today.

You're done when `python3 check_demo.py --recorded --transfer-minutes 30` prints `ch00 OK`. If you get stuck, the working code is in `book/ready/ch00`.

## What you are looking at

**Rasa Mantle** runs the conversation: instructions, tool requests and answers. A **tool** is a function the agent can ask to run. This agent's briefing tool produces four cards:

| Card | What it tells you |
|---|---|
| Flight | Aircraft position and a computed landing estimate |
| Weather | The forecast around the estimated arrival |
| Timeline | Whether arrival and an assumed transfer fit the meeting |
| Currency | Daily reference rates and their changes |

The position, forecast and rates were recorded on **22 October 2026**, so every card says **REPLAY**. The timeline is computed from those and from the meeting time and travel time you give. In this exercise “tomorrow” means 23 October 2026.

**SCRIPTED** means teaching code picks which tool to call. The agent engine and the cards are the real ones.

## Get the code

1. Get the code. The main route is to clone the repository:

   ```bash
   git clone https://github.com/RasaHQ/rasa-community-resources.git
   ```

   The alternative is the supplied ZIP. Unzip the supplied workshop package and open a terminal in its `software-factories-masterclass` folder. Initialize local Git metadata there so the demo can check that `.env` stays ignored:

   ```bash
   git init
   ```

   No GitHub account, remote repository or commit is needed. Follow [the prework](../PREWORK.md) if you need setup help.

   `PACK` is the `software-factories-masterclass` folder. After a clone it is `rasa-community-resources/workshops/software-factories-masterclass`. After unzipping it is the unzipped folder.

2. Set `PACK` and install the supplied code. The first export line is for a clone. If you unzipped, use the commented line instead:

   ```bash
   export PACK=~/rasa-community-resources/workshops/software-factories-masterclass   # after a clone
   # after unzipping, use this line instead: export PACK=/path/to/the/unzipped/software-factories-masterclass
   cd "$PACK/book/ready/ch00/demo"
   make help
   make setup
   make env
   ```

   Setup installs two Python 3.12 environments with pinned versions. `make env` creates a private `.env` file only if none exists, and never overwrites one.

3. Open `.env` in your editor. Put your issued license after `RASA_LICENSE=` and leave the model and voice entries empty for this scripted exercise. Add your OpenAI key when you want a model to choose the tools. Never paste a key into a chat, a URL or a terminal command, and never commit `.env`.

   ```bash
   make doctor
   ```

   You should see key **names** marked SET or MISSING, never values, and `Readiness check passed.` Missing model and voice keys are expected here. Fix any other error before you continue.

## See how it works

1. Start the **recorded** sources through the normal agent launcher:

   ```bash
   BRIEFING_RECORDED=1 make run-scripted
   ```

   The terminal explicitly says `recorded sources (REPLAY)`. Keep it running. Open [the local agent page](http://127.0.0.1:8942/) after it reports ready. This is the real Mantle Inspector, with the cards beside it.

2. Use the flight included in the recording:

   ```text
   United 1162 to EWR
   ```

   When asked for your meeting, answer:

   ```text
   The 6 pm meeting tomorrow.
   ```

   Four REPLAY cards appear. Read where each card says its data came from, and when it was recorded. The starting time to get from Newark to your meeting is **90 minutes**. That is a planning assumption, not traffic data.

3. In a second terminal, check the result before making your change:

   ```bash
   export PACK=~/rasa-community-resources/workshops/software-factories-masterclass   # after a clone
   # after unzipping, use this line instead: export PACK=/path/to/the/unzipped/software-factories-masterclass
   cd "$PACK/book/ready/ch00"
   python3 check_demo.py --recorded --transfer-minutes 30
   ```

   This must fail with `NOT DONE` and exit 1. The four cards are there, but the 90 minutes doesn't match the 30 you're about to ask for. If the demo isn't running, the command also fails, because it can't reach the page.

## Now change it

In the running conversation, ask:

```text
Allow 30 minutes to get into town.
```

The agent revises the timeline through its briefing tool. The flight, weather and currency cards stay the same, and so does your meeting. You don't edit any file.

You can ask for **120 minutes** instead. Use `--transfer-minutes 120` in the check.

## You are done when

From the second terminal, run your chosen check again:

```bash
python3 check_demo.py --recorded --transfer-minutes 30
```

It must exit 0 and print `ch00 OK`. That means the page shows four REPLAY cards and your new travel time. An empty board, a repeated card, three cards, an unavailable card or the old 90 minutes can't pass. Also check that the flight and meeting stayed the same.

Stop your own demo with Ctrl-C in its launcher terminal, or `make stop` from its `demo` folder. Do not kill someone else's process to free a port.

## Optional: try current public sources

After the recorded exercise, stop it. Run without the recorded flag:

```bash
make run-scripted
```

This needs the internet, and still makes no paid model request. Ask “I'm heading to New York. Which flights are already in the air?”, choose an actually returned flight, then state your meeting and transfer allowance. It searches a set of published New York routes. If none matches, give a flight you know is in the air. The recorded flight isn't in the air now.

Live positions, forecasts, computed estimates and daily rates carry different labels. A source that is down shows a reason, never an invented value. `python3 check_demo.py` without `--recorded` checks four available cards for this extra. You don't need it to finish the chapter.

## If it fails

- **License missing or refused:** use the issued license, not the sign-up confirmation. Do not share its value in a support report.
- **The check still says NOT DONE:** read the four cards. Each must say REPLAY, and the timeline must show your requested 30 or 120 minutes. Make the request in the conversation.
- **A port is occupied:** stop your own earlier run with `make stop`. The launcher doesn't stop anyone else's.
- **`.env` refused:** move it out of your clone, run `make env` to create a fresh one, put each key on its own line, and run `chmod 600 .env`. Never commit it.
- **A live source is unavailable:** return to the recorded exercise rather than calling an unavailable card complete.
- **You need help:** share the error sentence, your Python version and the command you ran. Never share your `.env` or your keys.

## Good to know

- The later chapters that run protected checks (3 to 7) need a Mac, because they use `sandbox-exec`. This chapter was run on macOS with Python 3.12. Other systems haven't been tried. Pair with someone on a Mac if you need to.
- No model is reasoning in this exercise. Teaching code picks the tools, and the recorded data never opens a connection to a source or a model.
- A present license must still be accepted when the agent engine starts, so a passing `make doctor` doesn't guarantee a start.
- Spoken input is not part of this chapter. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. Seeing text cards doesn't show that voice works.
- Model or voice demonstrations are not part of this book's checks. They need a reviewed plan with a named model, limits and an expected cost.

## What you just learned

You ran an agent that builds a four-card briefing from public data, and you changed its answer by asking in plain words. Every value on a card says where it came from.

Next: [Chapter 1](01-what-a-mantle-agent-is.md) shows the files that make this conversation work.
