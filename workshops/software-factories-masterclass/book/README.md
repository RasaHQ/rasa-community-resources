# The software factories book

A hands-on book that takes you from a running Rasa Mantle agent to a dark software factory that builds a new
card for that agent. You can follow it alone from a clone of this repository. You do not need to have attended
the workshop.

A coding agent says its change works, and you have no time to read every line it changed. A software factory checks the change for you, with tests the agent never sees. You build one here, chapter by chapter, and watch it accept a good change and reject a bad one.

Time: each chapter opens with its own estimate. Chapter 0 takes about 5 minutes to install and then about 20. Chapters 1 to 8 take about 10, 10, 25, 30, 20, 15, 15 and 20. Every chapter ends with a check that prints `chNN OK`, so you always know whether you're done. If a chapter goes wrong, start it again from its ready folder.

## What you need first

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- A free Rasa Developer Edition license for chapter 0, set as `RASA_LICENSE` in your own terminal
- An OpenAI API key, set as `OPENAI_API_KEY`, only if you want the optional live builder run in chapter 5. Every `chNN OK` check runs without it.
- A Deepgram key is optional and only adds voice
- About 3 GB of disk space and a network connection for the first install

Keys and the license go in the example's Git-ignored `.env` (created by `make env` with mode 600) or in your shell. Never commit that file, and never paste a key anywhere else.

Clone this repository with Git. A ZIP download is not supported.

## How the chapters work

Every chapter opens with a short scene, then a **Time** line and what you need. After that it has the same parts:

1. **See how it works.** Run the working code, watch what happens and read the two or three files that matter.
2. **Now change it.** Ask for a change. In a factory you do that by changing the task, and the gates decide, with no code written by hand. Chapters 1 and 2 are short reading chapters, and their change step follows after the class.
3. **You're done when.** A real command that prints `chNN OK`. In chapters 3 to 8 it fails before you make your change and passes after.
4. **If you get stuck.** The working code for the chapter is in its ready folder under `ready/`, so you can start any chapter without doing the earlier ones. Chapters 1 and 2 use the chapter 0 folder.

Chapters 3, 4, 6 and 7 each work in their own folder (`my-factory-ch03` and so on), next to your clone and outside it, copied from the chapter's ready folder. `REPO` in the commands means the folder where you cloned this repository, for example `export REPO=~/rasa-community-resources`.

## The chapters

| Chapter | Title | You build | You are done when |
| --- | --- | --- | --- |
| [0](00-run-the-finished-agent.md) | Run the agent you will learn to build | Run the recorded briefing agent, see four REPLAY cards, then ask it to change its transfer allowance | `ch00 OK`: `check_demo.py` shows four REPLAY cards and your 30 minute allowance |
| [1](01-what-a-mantle-agent-is.md) | What a Rasa Mantle agent is | Find the agent, the skill and the tool in the folder (short chapter: the change step follows after the class) | `ch01 OK`: you can point to the agent, the skill and the tool |
| [2](02-cards-from-real-sources.md) | Cards from real sources | Find where one card's data comes from and the rules that label it (short chapter: the change step follows after the class) | `ch02 OK`: you can point to the skill, the tool and one reader |
| [3](03-a-factory-starts-with-a-task.md) | A factory starts with a task | See a task judged, then set your own limit and let the builder's attempt be judged | `ch03 OK`: the builder's attempt for your task is accepted |
| [4](04-acceptance-before-code.md) | Acceptance before code | See the tests that judge the card, lock them for your task and watch them accept the attempt | `ch04 OK`: the tests fail on the baseline for the right reasons, the fingerprints match and the attempt is accepted |
| [5](05-the-builder.md) | The builder, on the OpenAI Agents API | A builder session with file tools confined to a scratch copy | The builder produces a change you can check in an offline run, and a live run is the extra |
| [6](06-the-gates-and-the-decision.md) | The gates and the decision | The gate runner and the recorded decision | `ch06 OK`: the builder's attempt for your task is accepted and the bad one is rejected, offline |
| [7](07-integrate-and-run-it-dark.md) | Integrate and run it dark | Integration, then the whole loop | `ch07 OK`: your change is integrated and the card shows your number of currencies, offline |
| [8](08-going-further.md) | Going further | Policy, measurement, recovery and escalation | The measure and recover commands run on your own factory |

The book teaches the factory one part per chapter. The finished factory in `../factory/` is the reference result you can compare with.

## What to know before you start

- Chapters 3 to 7 run their protected checks on macOS, because the no-network check uses `sandbox-exec`. On Linux or Windows, pair with someone on a Mac, or follow along on screen. Chapter 0 was run on macOS, and other systems haven't been tried. Chapters 1 and 2 only read files, and chapter 8 uses only Python's standard library. On another system the gate says `could not run: this check needs macOS` and exits 2 before it judges anything, so a good attempt is never shown as rejected.
- A factory that accepts a change has judged it against the tests you wrote. It has not proved the change is right.
- Chapters 3, 4, 6 and 7 build the factory step by step. The finished factory is in `../factory/` and the task is in `../factory/a6-market-watchlist/`.
- Live data and voice depend on public sources and your own keys, and they can fail on the day. Each chapter says
  what to do when they do.
