# Build a software factory that checks an AI agent's changes

A workshop by Rod Rivera, using Rasa Mantle and the OpenAI Agents API.

## The problem this workshop solves

Your flight lands at 5 pm. Your meeting across town starts at 6 pm. Will you make it? To find out, you would open a flight tracker, a weather site, a map and a currency converter, and still have to work out the answer yourself.

An AI agent can answer that question in one place. In this workshop you run such an agent: it shows four cards, for the flight, the weather at landing, your arrival timeline and the exchange rate.

Then comes the harder question. Coding agents can now change software for you, but they also tell you a change works when it doesn't. Nobody has time to read every line they write. So how do you let an agent change your agent safely?

The answer you will build is a **software factory**: a fixed set of steps that turns a written request into a change, checks that change with tests the coding agent can't see or edit, and then decides ACCEPT or REJECT. You will watch it accept a good change and reject a bad one.

## What you will be able to do afterwards

- Run an AI agent built with Rasa Mantle, and change how it behaves just by asking it.
- Write a request for a change that a machine can check.
- Protect the tests that decide, so the agent making the change can't quietly bend them.
- Read a factory's decision, and explain why ACCEPT or REJECT was the right answer.
- Explain what a "dark" factory is: one where people set the rules and machines do the building and checking, with anything unusual sent back to a person.

You don't need to know Rasa, Mantle or the OpenAI Agents API before you start. Every word is explained when it first appears.

## Before you start (about 10 minutes, plus a short wait)

You need:

- A laptop. Chapters 3 to 7 need a Mac, because the factory's protective checks use a macOS feature. No Mac? Pair up with someone who has one, or follow **Track B** in the participant guide, which works with Python 3.12 on any system (Windows is untested).
- Python 3.12, [uv](https://docs.astral.sh/uv/), Git and Make.
- A free [Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). Request it first, because the key arrives by email. The form's confirmation page is not the key.
- An OpenAI key is **not** needed. It is only used by one optional extra in chapter 5.

Get the code:

```bash
git clone https://github.com/RasaHQ/rasa-community-resources.git
cd rasa-community-resources/workshops/software-factories-masterclass
```

This folder is the one the book calls `PACK`.

## Choose how you want to learn

**In the room, or with about two hours:** follow the [participant guide](PARTICIPANT-GUIDE.md). It takes you through a few checkpoints, tells you what you should see at each one, and what to do if you don't.

**On your own, at your own pace (about three hours):** work through [the book](book/README.md), one chapter at a time. Each chapter starts with a short scene, tells you how long it takes, has you run something that already works, then asks you to change it. Each chapter ends with a check that prints `chNN OK`, so you always know when you're done. If you get stuck, every chapter has a ready-made folder to start again from.

| Chapter | What you do | Time |
|---|---|---|
| [0](book/00-run-the-finished-agent.md) | Run the agent you will learn to build | about 5 minutes to install, then 20 |
| [1](book/01-what-a-mantle-agent-is.md) | See what a Rasa Mantle agent is made of | about 10 minutes |
| [2](book/02-cards-from-real-sources.md) | See how each card says where its data came from | about 10 minutes |
| [3](book/03-a-factory-starts-with-a-task.md) | Give the factory a written task | about 25 minutes |
| [4](book/04-acceptance-before-code.md) | Lock the tests before any change is made | about 30 minutes |
| [5](book/05-the-builder.md) | Ask a builder to make the change | about 20 minutes |
| [6](book/06-the-gates-and-the-decision.md) | Watch the factory accept one change and reject another | about 15 minutes |
| [7](book/07-integrate-and-run-it-dark.md) | Bring an accepted change into the product, with nobody reviewing each line | about 15 minutes |
| [8](book/08-going-further.md) | Measure results and recover from a crash without guessing | about 20 minutes |

## Words you will meet

- **Rasa Mantle:** the framework the travel agent is built with. It runs the conversation and decides when to call a tool.
- **Tool:** a function the agent can ask to run, such as "find flights heading to New York".
- **OpenAI Agents API:** an OpenAI service that runs a model session for you. Here it powers the builder, the coding agent that makes changes. (It is not the same thing as the OpenAI Agents SDK, a separate library.)
- **Acceptance test:** a check that the change does what was asked. The builder never sees or edits the acceptance tests that decide.
- **Software factory:** the fixed steps from a written request to a checked decision, the same way every time.

## What this workshop does not show yet

Being honest about the limits is part of the method:

- The agent's choice of tools is **scripted** in the exercises, so the results are repeatable. The flight, weather and rate data are real, or a labeled recording.
- **Voice:** a test with recorded audio failed on the second turn, so type your requests. Speaking into a microphone is untested.
- The full journey, where you **ask by voice** for a new agent and the factory builds and releases it, is the next step. [BUILD-CONTRACT.md](BUILD-CONTRACT.md) describes what it needs.

Chapter 0 runs on Rasa Pro 3.21.0. The standalone example in `examples/` stays on 3.21.0.dev5 for now.

## For facilitators

Use the [run sheet](RUN-SHEET.md) for timing and the [presenter notes](slides/PRESENTER-NOTES.md) for each slide. The slides are in `slides/index.html` and as a [PDF](slides/masterclass-slides.pdf). The [technical audit](TECHNICAL-AUDIT.md) lists exactly what was tested.

Other folders here (`factory/`, `openai-mcp/`, `brief-me-before-i-fly/`, `archive/`) are earlier material and are not needed for this workshop. The standalone version of the travel agent, with its own [self-paced guide](../../examples/mantle-flight-briefing-openai-agents/SELF-PACED-GUIDE.md), is in `examples/mantle-flight-briefing-openai-agents/`.
