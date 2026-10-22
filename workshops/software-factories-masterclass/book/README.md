# The software factories book

A hands-on book that takes you from a running Rasa Mantle agent to a dark software factory that builds a new
card for that agent. You can follow it alone from a clone of this repository. You do not need to have attended
the workshop.

## What you need first

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- A free Rasa Developer Edition license, set as `RASA_LICENSE` in your own terminal
- Your own OpenAI API key, set as `OPENAI_API_KEY` in your own terminal
- A Deepgram key is optional and only adds voice
- About 3 GB of disk space and a network connection for the first install

Keys and the license go in the example's Git-ignored `.env` (created by `make env` with mode 600) or in your shell. Never commit that file, and never paste a key anywhere else.

Clone this repository with Git. A ZIP download is not supported.

## How the chapters work

Every chapter has the same parts:

1. **Goal**, in one sentence, and **You need first**, which names the earlier chapters it builds on.
2. **Steps**, numbered, each with the exact command and what you should see.
3. **You are done when**, a real command that passes. If it does not pass, you are not done.
4. **Ready folder**, the working code for that chapter under `ready/`, so you can start at any chapter
   without doing the earlier ones.

Each chapter builds on the one before it, and every chapter has its own ready folder, so you can start at any chapter. Each "you are done when" check fails in the chapter's ready folder and passes after you make the change.

## The chapters

| Chapter | Title | You build | You are done when |
| --- | --- | --- | --- |
| [0](00-run-the-finished-agent.md) | Run the finished agent | Clone, set up and run the briefing agent, and see its four cards | The doctor passes and the four recorded cards show (a live flight is the extra, not the check) |
| [1](01-what-a-mantle-agent-is.md) | What a Rasa Mantle agent is | Read and change the briefing skill and its tool | The changed skill trains and its test passes |
| [2](02-cards-from-real-sources.md) | Cards from real sources | How cards, the renderer and the four public readers fit together | The card test passes with the label rules held |
| [3](03-a-factory-starts-with-a-task.md) | A factory starts with a task | See a task judged, then set your own limit and let the builder's attempt be judged | `ch03 OK`: the builder's attempt for your task is accepted |
| [4](04-acceptance-before-code.md) | Acceptance before code | See the tests that judge the card, lock them for your task and watch them accept the attempt | `ch04 OK`: the tests fail on the baseline for the right reasons, the fingerprints match and the attempt is accepted |
| [5](05-the-builder.md) | The builder, on the OpenAI Agents API | A builder session with file tools confined to a scratch copy | The builder produces a candidate change in an offline run, and a live run is the extra |
| [6](06-the-gates-and-the-decision.md) | The gates and the decision | The gate runner and the recorded decision | `ch06 OK`: the builder's attempt for your task is accepted and the bad one is rejected, offline |
| [7](07-integrate-and-run-it-dark.md) | Integrate and run it dark | Integration, then the whole loop | `ch07 OK`: your change is integrated and the card shows your number of currencies, offline |
| [8](08-going-further.md) | Going further | Policy, measurement, recovery and escalation | The measure and recover commands run on your own factory |

The book teaches the factory one part per chapter. In each chapter you first see a working part run, then you change your own task and the factory's gates decide. The finished factory in `../factory/` is the reference result you can compare with.

## How each chapter works
Every chapter ships its own working code in a ready folder under `ready/`, so nobody starts from zero. A chapter has three parts: **See how it works**, where you run the code, watch what happens and read the two or three files that matter. **Now change it**, where you ask for a change (in a factory, by changing the task) and the gates decide, with no code written by hand. And **You are done when**, a real command that passes.

Chapters 3, 4, 6 and 7 each work in their own folder (`my-factory-ch03` and so on), next to your clone and outside it, copied from the chapter's ready folder. `REPO` in the commands means the folder where you cloned this repository, for example `export REPO=~/rasa-community-resources`.

## Honest limits

- Chapters 3 to 7 run their protected checks on macOS. On Linux or Windows, pair with someone on a Mac, or follow along on screen. Everything else works on any laptop. The reason is that the no-network check uses `sandbox-exec`. On another system the gate says `could not run: this check needs macOS` and exits 2 before it judges anything, so a good attempt is never shown as rejected.
- A factory that accepts a change has judged it against the tests you wrote. It has not proved the change is right.
- Chapters 3, 4, 6 and 7 build the factory step by step. The finished factory is in `../factory/` and the task is in `../factory/a6-market-watchlist/`.
- Live data and voice depend on public sources and your own keys, and they can fail on the day. Each chapter says
  what to do when they do.
