# Rasa Community Resources

**Tutorials, example projects, and reference code for practitioners building and operating agents with Rasa.**

This is the code companion to [rasa.community](https://rasa.community/).

---

## Summarized

If you learn by reading, start with [rasa.community](https://rasa.community/). If you learn by doing, start here. Every resource in this repository is a directory you can run in full, study, or copy piece by piece into your own project. Each one states the date it was last verified and the versions it was verified against.

---

## What this is

- **Tutorials** — end-to-end walkthroughs, each self-contained, each runnable.
- **Example projects** — complete agents you can clone and adapt, not fragments.
- **Reference code** — patterns for the problems that recur: tool design, evaluation, deployment, observability, human handover.
- **Workshop material** — slides, exercises, and solutions from community sessions and conference workshops.

## What this is not

- **Not the product documentation.** The canonical reference for the framework is [rasa.com/docs](https://rasa.com/docs/). This repository is educational material.
- **Not the Rasa framework itself.** Rasa Pro is a commercial framework. This repository contains community-facing teaching material only; installing and running it requires a licence key, which is free for developers (see below).
- **Not a support channel.** Product issues belong in the product repositories or with Rasa support. Questions about the material here belong in [Discussions](../../discussions/) or in the community Discord.

---

## Start here

**If you have never run Rasa before.** Request a free [Developer Edition licence key](https://rasa.com/rasa-pro-developer-edition-license-key-request/) — 1,000 conversations per month, no cost — then work through `tutorials/getting-started/`.

**If you are building something specific.** Go to the repository map below and find the closest example project. Clone it, run it, then change one thing at a time.

**If you want the people.** Apply to the [community](https://info.rasa.com/community/). The application includes access to the Discord, where the practitioners maintaining much of this material spend their time.

**If you want to learn the discipline.** Rod writes about harness engineering at the [rasa.community/library/](https://rasa.community/library/) and at [profrod.ai](https://profrod.ai).

---

## Repository map

| Path | What it holds |
|---|---|
| `tutorials/` | Step-by-step walkthroughs. One directory per tutorial, each with its own README and runnable code. |
| `examples/` | Complete example agents. Clone-and-run. |
| `patterns/` | Small, focused reference implementations of recurring problems. |
| `workshops/` | Slides, exercises, and solutions from community and conference sessions. |
| `snippets/` | Short pieces of code that are useful but too small to be a pattern. |

---

## How to read a resource in this repository

Every directory contains a `README.md` that opens with a block like this:

```
Author:        Rod Rivera
Assessed on:   2026-08-13
Verified with: rasa-pro 3.x, Python 3.11, uv 0.5
Audience:      Practitioners who have deployed at least one agent
Time:          45 minutes
```

Read the **Assessed on** date first. If it is more than six months old, likely the version number has moved on. Feel free to open an issue if something no longer runs. Material that cannot be re-verified is archived.

---

## Requirements

Resources here assume:

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) for dependency management (`uv add rasa-pro`)
- A `RASA_LICENSE` key in your environment — the [Developer Edition](https://rasa.com/rasa-pro-developer-edition-license-key-request/) key is free
- An LLM provider key, typically `OPENAI_API_KEY`

Individual resources state their own additional requirements.

---

## Contributing

Contributions are welcome, and contributors are credited by name in the resource they contribute to.

The three things that matter most:

1. **One resource per pull request.** A tutorial, an example, or a pattern — not a mix.
2. **It has to run.** Include the versions you verified against and the date you verified them. A contribution that works on your machine and nowhere else is a maintenance liability rather than a gift.
3. **Write for peers.** The reader is a working practitioner. Do not over-explain the basics and do not skip the failure modes. If something breaks in production, say what breaks and why.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full detail, and [MAINTAINERS.md](MAINTAINERS.md) for who reviews what and how long it takes.

If you have built something with Rasa that belongs in the [showcase](https://rasa.community/showcase/), the route is the [community application](https://info.rasa.com/community/) rather than a pull request here.

---

## Going further

- **[Rasa University](https://rasa.com/university/)** — structured courses and the Developer Certification.
- **[rasa.community](https://rasa.community/)** — our community hub, heroes programme, and educational library.
- **[rasa.com/docs](https://rasa.com/docs/)** — the product documentation.

---

## Maintainers

This repository is maintained by **[Rod Rivera](https://profrod.ai/)**, DevRel at Rasa, Professor of the Practice at ITAM, and lecturer at Nebius Academy. He writes about harness engineering and the operation of long-running agents at [profrod.ai](https://profrod.ai/).

Full ownership, review scope, and response expectations are in [MAINTAINERS.md](MAINTAINERS.md).

## Licence

The tutorials, examples, and reference code in this repository are released under the Apache License 2.0 — see [LICENSE](LICENSE). This licence covers the teaching material in this repository only. Rasa Pro is a commercial framework governed by its own licence terms.