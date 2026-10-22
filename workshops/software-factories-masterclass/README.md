# Build a software factory that checks an AI agent's changes

A workshop by Rod Rivera, using Rasa Mantle and the OpenAI Agents API.

Today: build, reject and accept a change. Next: build it by voice.

## The problem this workshop solves

Your flight lands at 5 pm. Your meeting across town starts at 6 pm. Will you make it? To find out, you would open a flight tracker, a weather site, a map and a currency converter, and still have to work out the answer yourself.

An AI agent can help answer that question in one place. In this workshop you run such an agent: it shows four cards, for the flight, the weather at landing, your arrival timeline and the exchange rate. The timeline uses your transfer allowance. It is an estimate, not a live route prediction.

Then comes the harder question. Coding agents can change software for you, but they also tell you a change works when it doesn't. Nobody has time to read every line they write. So how do you let an agent change your agent safely?

The answer you will build is a **software factory**: a fixed set of steps that turns a written request into a change, checks that change with tests the coding agent can't see or edit, and then decides ACCEPT or REJECT. You will watch it accept a good change and reject a bad one.

## What you will be able to do afterwards

- Run the supplied travel agent built with Rasa Mantle.
- Write a request for a change that a machine can check, then run a separate builder exercise.
- Protect the tests that decide, so the agent making the change can't quietly bend them.
- Read a factory's decision and explain why ACCEPT or REJECT was the right answer.
- Explain a “dark” factory: people set the rules and machines do routine building and checking, with exceptions sent back to a person.

You don't need to know Rasa, Mantle or the OpenAI Agents API before you start. Read the [beginner introduction](BEGINNER-PRIMER.md) for the same explanations used in the slides.

## Before you start (about 10 minutes, plus a short wait)

You need:

- A laptop. Chapters 3 to 7 need a Mac for the protective code checks. No Mac? Pair with someone who has one, or follow **Track B** in the participant guide: Python 3.12 only; 3.13 and 3.14 stop with NOT_READY. Windows is untested.
- Python 3.12, [uv](https://docs.astral.sh/uv/), Git and Make.
- A free [Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). Request it first: the form's confirmation page is not the key, and the key reaches you after you submit.
- An OpenAI API key. Rasa Mantle has no model of its own: in live mode it asks a language model, OpenAI by default, to understand what you type and to choose a tool. The scripted mode (chapter 0 and the other exercises) runs without a key, because teaching code chooses the tools, so you can start while your key is being set up.
- Chapter 5 has an optional paid live builder using the Agents API and `gpt-6-astra`.

Get your own copy. On GitHub, click **Fork** on [RasaHQ/rasa-community-resources](https://github.com/RasaHQ/rasa-community-resources), then clone your fork:

```bash
git clone https://github.com/YOUR-GITHUB-NAME/rasa-community-resources.git
cd rasa-community-resources/workshops/software-factories-masterclass
export PACK="$PWD"
```

This folder is the one the book calls `PACK`. Everything here is plain Markdown and code, so you can open it in your editor and point your coding agent, such as Claude Code or Codex, at a chapter. Keep the deciding acceptance tests outside the builder's readable and writable workspace. Your changes stay in your fork.

## Choose how you want to learn

**In the room, or with about two hours:** follow the [participant guide](PARTICIPANT-GUIDE.md). It tells you what to run, what you should see and what to do if you don't.

**On your own, at your own pace (about three hours):** work through [the book](book/README.md), one chapter at a time. Each chapter introduces the problem, gives you something to run and asks you to change it. Ready-made folders let you restart. Chapter checks tell you when you've met the learning goal; a factory ACCEPT alone does not always mean a chapter is done.

| Chapter | What you do | Time |
|---|---|---|
| [0](book/00-run-the-finished-agent.md) | Run the agent you will learn to build | about 5 minutes to install, then 20 |
| [1](book/01-what-a-mantle-agent-is.md) | See what a Rasa Mantle agent is made of | about 10 minutes |
| [2](book/02-cards-from-real-sources.md) | See how each card says where its data came from | about 10 minutes |
| [3](book/03-a-factory-starts-with-a-task.md) | Give the factory a written task | about 25 minutes |
| [4](book/04-acceptance-before-code.md) | Lock the tests before a change is made | about 30 minutes |
| [5](book/05-the-builder.md) | Ask a builder to make the change | about 20 minutes |
| [6](book/06-the-gates-and-the-decision.md) | Watch the factory accept and reject changes | about 15 minutes |
| [7](book/07-integrate-and-run-it-dark.md) | Integrate an accepted change locally | about 15 minutes |
| [8](book/08-going-further.md) | Measure results and recover from a crash | about 20 minutes |

In Track A checkpoint 3, the supplied task has `"limit": 2`. Its first build can satisfy that task, but `check_build.py attempts/first` prints **NOT DONE**: the learning exercise asks you to change the limit to **1 or 3 and build fresh**. Only then should the chapter check print `ch05 OK`.

## Words you will meet

- **Rasa Mantle:** the framework the travel agent is built with. It coordinates conversations, skills and tools. A skill groups instructions and tools for a particular job.
- **Tool:** a function the agent can ask to run, such as finding flight information.
- **Deepgram:** the speech service used in the voice extension to turn audio into text and text into audio.
- **OpenAI Agents API:** an OpenAI service that manages an agent session. Here it powers the optional live coding builder. It is different from the Agents SDK, a separate framework.
- **Acceptance test:** a check that the change does what was asked. The builder may see example tests. It never sees or edits the acceptance tests that decide.
- **Software factory:** repeatable steps from a written request to a checked decision.

## What this workshop does not show yet

- With a model choosing the tools, the travel agent was slow to answer in our rehearsal on 22 October. The scripted mode is the reliable path today.
- Tool selection is **scripted** in the exercises so results are repeatable. Source data may be fetched, recorded or unavailable; read the card's label.
- **Voice:** on 22 October a recorded-audio test failed on the second turn. Type your requests. Microphone use is untested.
- The travel agent and coding builder run separately. Asking the travel agent to change its own code is not a completed capability.
- The full journey, where you **ask by voice** for a new agent and the factory builds and releases it, is the next step. [BUILD-CONTRACT.md](BUILD-CONTRACT.md) describes what it needs.

Chapter 0 runs on **Rasa Pro 3.21.0**. The standalone example in `examples/` stays on **3.21.0.dev5**.

## For facilitators

Use the [run sheet](RUN-SHEET.md), [presenter notes](slides/PRESENTER-NOTES.md), [slides](slides/index.html) and [PDF](slides/masterclass-slides.pdf). The [technical audit](TECHNICAL-AUDIT.md) distinguishes tests run here from earlier course-team evidence. [Learning checkpoints](LEARNING-CHECKPOINTS.md) provide explanation prompts.

Other folders (`openai-mcp/`, `brief-me-before-i-fly/`, `archive/`) are earlier material and are not required. The standalone travel agent has its own [self-paced guide](../../examples/mantle-flight-briefing-openai-agents/SELF-PACED-GUIDE.md).
