# The software factories book

A hands-on book that takes you from a running Rasa Mantle agent to a dark software factory that builds a new
card for that agent. You can follow it alone from a clone of this repository. You do not need to have attended
the workshop.

## What you need first

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- A free Rasa Developer Edition licence, set as `RASA_LICENSE` in your own terminal
- Your own OpenAI API key, set as `OPENAI_API_KEY` in your own terminal
- A Deepgram key is optional and only adds voice
- About 3 GB of disk space and a network connection for the first install

Keys and the licence are read from your environment only. Never put one in a file in this repository.

## How the chapters work

Every chapter has the same parts:

1. **Goal**, in one sentence, and **You need first**, which names the earlier chapters it builds on.
2. **Steps**, numbered, each with the exact command and what you should see.
3. **You are done when**, a real command that passes. If it does not pass, you are not done.
4. **Checkpoint**, a finished folder for that chapter under `checkpoints/`, so you can start at any chapter
   without doing the earlier ones.

Each chapter builds on the one before it, and every chapter after Chapter 0 can start from the earlier checkpoint.

## The chapters

| Chapter | Title | You build | You are done when |
| --- | --- | --- | --- |
| [0](00-run-the-finished-agent.md) | Run the finished agent | Clone, set up and run the briefing agent, and see its four cards | The doctor shows your licence and key as SET, and the four cards show for a live flight |
| [1](01-what-a-mantle-agent-is.md) | What a Rasa Mantle agent is | Read and change the briefing skill and its tool | The changed skill trains and its test passes |
| [2](02-cards-from-real-sources.md) | Cards from real sources | How cards, the renderer and the four public readers fit together | The card test passes with the label rules held |
| [3](03-the-factorys-parts.md) | The factory's parts | The task, the protected acceptance suite, the gates and the decision | `factory.py` ACCEPTs the good candidate and REJECTs the bad ones |
| [4](04-write-the-task-and-its-acceptance-first.md) | Write the task and its acceptance first | The market card task and its hidden suite, before any code | The suite fails on the baseline, for the right reasons |
| [5](05-the-builder.md) | The builder, on the OpenAI Agents API | A builder session with file tools confined to a scratch copy | The builder produces a candidate change |
| [6](06-let-the-factory-build-the-card.md) | Let the factory build the market card | The whole loop, from task to ACCEPT and integration | The market card appears in your own running agent |
| [7](07-going-dark.md) | Going dark | Policy, measurement, recovery and escalation | The measure and recover commands run on your own factory |

## Honest limits

- A factory that accepts a change has judged it against the tests you wrote. It has not proved the change is right.
- Chapters 3, 4 and 6 use the factory in `../factory/` and the task in `../factory/a6-market-watchlist/`.
- Live data and voice depend on public sources and your own keys, and they can fail on the day. Each chapter says
  what to do when they do.
