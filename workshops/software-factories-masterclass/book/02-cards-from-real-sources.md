> **22 October revision:** Start with [the participant guide](../PARTICIPANT-GUIDE.md) for the three-hour route, current API distinctions, and platform requirements. These chapters are reference exercises; their checks do not certify the complete voice-to-build-to-voice journey.

# Chapter 2: Cards from real sources

Picture a card that says "live" beside a rate that updates once a day. A traveler trusts it and plans around it. In about 10 minutes you'll find the code that stops that, by labeling every card with where its data came from and how fresh it is.

Time: about 10 minutes. You need: the Chapter 0 ready folder and a terminal. You only read files here, so there's no key or account. This chapter has no "Now change it" step. That step comes after the class.

You're done when the listing command at the end prints `ch02 OK`. If you get stuck, open `book/ready/ch00/demo` and run the commands from there.

## Where a card's data comes from

The agent never writes the numbers on a card. A **reader** is code that fetches one kind of data from a public source, such as the position of a plane or a weather forecast. The briefing has four readers, one for each card:

| Card | Reader | Label on the card |
|---|---|---|
| Flight | Reads an aircraft's observed position | PROVIDER DATA |
| Weather | Reads the forecast near the landing time | PROVIDER DATA |
| Timeline | Computes your margin from the landing estimate, your meeting and the travel allowance | COMPUTED |
| Currency | Reads daily exchange reference rates | PROVIDER DATA |

A card built from a recorded example gets the label REPLAY instead, so nobody mistakes it for live data.

## Get to the folder

```bash
export PACK=/absolute/path/to/software-factories-masterclass
cd "$PACK/book/ready/ch00/demo"
```

## See how it works

1. Find the code in this folder that asks the readers for data:

   ```bash
   grep -E "^class " briefing/public_sources.py briefing/live_public_sources.py
   ```

   You see `PublicSourcesRunner` and `LivePublicSourcesRunner`. They call the readers and hand each result to a card. The readers themselves come from `zeocore`, the Python package that holds the card code. Chapter 0 installed it.

2. See which readers the live runner imports:

   ```bash
   grep -E "^from zeo_core.integrations.briefing_sources" briefing/live_public_sources.py
   ```

   Each line names a reader module, such as `flight` and `timeline`.

3. Find the label rules:

   ```bash
   grep -n 'label = ' project/lib/card_text.py
   ```

   You see one line that chooses REPLAY, COMPUTED or the provider label, which the card shows as PROVIDER DATA. The label depends on where the data came from, never on how the agent describes it.

4. Find the freshness lines:

   ```bash
   grep -n "Freshness:" project/lib/card_text.py
   ```

   Each kind of card says how fresh its data is, in its own words. The flight card says it is a live position. The weather card says it is a forecast, not an observation. The timeline says it is computed. A replay card has no freshness line, because it makes no claim about now.

Now follow one card. A reader fetches data and records where it came from. The card text adds the label and the freshness line. A missing source gives an unavailable card with a reason, never an invented value.

## You are done when

Run this in the `demo` folder:

```bash
( set -e; ls -1 project/skills/briefing/skill.md briefing/mcp_app.py briefing/public_sources.py project/lib/card_text.py; echo "ch02 OK" )
```

It lists the skill, the tool, one reader runner and the card text rules, then prints `ch02 OK`. It checks that the files are present. Reading them is your part.

## What you just learned

Every card carries a label that says where its data came from, and most carry a line that says how fresh it is. A source that is down gives an unavailable card with a reason, never an invented value.

Next: [Chapter 3](03-a-factory-starts-with-a-task.md) starts the factory itself, with a task and tests that judge the change.
