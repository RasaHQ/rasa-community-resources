# Build a software factory with Rasa Mantle

Author: Rod Rivera.

Tested by the course team on 22 October 2026 on macOS with Python 3.12, uv and a Rasa Developer Edition license. From a fresh clone of main (`8feb87f5`), Chapter 0 passed setup, the recorded flight-and-meeting journey in the Mantle Inspector, and the change from a 90-minute to a 30-minute transfer allowance (`ch00 OK`). Chapter 3 passed on a Mac with a fresh environment: the scripted builder changed the limit to two, the protected checks accepted it, and completion printed `ch03 OK`.

Time: 3 hours in the room; on your own, about 3 hours. The chapters total about 165 minutes, plus about 5 minutes for the first install.

You ask an agent to brief you before a flight. It shows four cards: the flight, the weather, your arrival timeline and the market card, which lists exchange rates. You’ll run that agent, then build a small software factory that gives a builder a task for the market card, checks its changes against rules it cannot edit, and decides whether to accept them. Along the way, you’ll try a broken change and see why passing the builder’s own tests is only the beginning.

## Start here

Open the [book](book/README.md) and begin with Chapter 0. Each chapter gives you the files, commands and completion check for its exercise.

- [Slides](slides/): open `slides/index.html` for the classroom presentation.
- [Run sheet](RUN-SHEET.md): the session sequence and demo instructions for facilitators.
- [Factory](factory/): the market card task and its protected checks.
- [Example agent](../../examples/mantle-flight-briefing-openai-agents/): the flight briefing project.

## What today does not show

You won’t see a live model choosing tools. The session shows a recording of the model building the change, then runs a scripted builder live. Voice has not been tested end to end, so the facilitator types the requests. The new market card has not been installed in the running demo.

## Earlier material in this folder

`FACILITATOR.md`, `FACILITATOR-CARD.md`, `OFFLINE-OPENING.md`, `PREWORK.md`, `brief-me-before-i-fly/` and `openai-mcp/` belong to the earlier version and are not used today. The [run sheet](RUN-SHEET.md) replaces those session instructions.
