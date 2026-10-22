# Chapter 2: Cards from real sources

**Goal:** look at one card, find the code that fetched its data, and read the rules that label it.

**You need first:** Chapter 1, and the checkpoint folder from Chapter 0. You only read files here. Nothing runs, and no key or account is needed.

This chapter is short on purpose. It shows you where a card's data comes from. A later "Now change it" step, where you add one field to a card and check the label rules, follows after the class.

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
export REPO=~/rasa-community-resources
cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00/demo"
```

## See how it works

1. Find the code in this folder that asks the readers for data:

   ```bash
   grep -E "^class " briefing/public_sources.py briefing/live_public_sources.py
   ```

   You see `PublicSourcesRunner` and `LivePublicSourcesRunner`. They call the readers and hand each result to a card. The readers themselves come from the Core package that Chapter 0 installed.

2. See which readers the live runner imports:

   ```bash
   grep -E "^from zeo_core.integrations.briefing_sources" briefing/live_public_sources.py
   ```

   Each line names a reader module, such as `flight` and `timeline`.

3. Find the label rules:

   ```bash
   grep -n 'label = ' project/lib/card_text.py
   ```

   You see one line that chooses REPLAY, COMPUTED or PROVIDER DATA. The label depends on where the data came from, never on how the agent describes it.

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

You can now point to the skill, the tool and one reader in the folder.

## What comes next

The "Now change it" half of this chapter, where you add a field to a card, follows after the class. Chapter 3 starts the factory itself: a task, and tests that judge the change.
