# Rasa Community Resources

**Tutorials, example projects, and reference code for practitioners building and operating agents with Rasa.**

This is the code companion to [rasa.community](https://rasa.community/). Every resource is a directory you can run in full, study, or copy piece by piece into your own project. Each one states who wrote it, when it was last verified, and which versions it was verified against.

---

## Start here

**New to Rasa Skills / Mantle voice agents.** Request a free [Developer Edition licence key](https://rasa.com/rasa-pro-developer-edition-license-key-request/), then clone and run the flagship Atlas travel agent:

1. [`examples/mantle-voice-agent`](examples/mantle-voice-agent) — finished agent you can run with `make install` → `make inspect`
2. Hosted walkthrough: [Build a Voice AI Agent with Rasa Skills](https://rasa.community/library/tutorials/voice-ai-agent/)

**Building something specific.** Browse [Featured resources](#featured-resources) or open the category catalog that matches your goal ([examples](examples/README.md), [tutorials](tutorials/README.md), [patterns](patterns/README.md)).

**Looking for people.** Apply to the [community](https://info.rasa.com/community/) for Discord access. Practitioners who maintain and extend this material spend time there.

**Want the discipline behind the material.** The community library lives at [rasa.community/library/](https://rasa.community/library/) and Rod also writes about harness-engineering at [profrod.ai](https://profrod.ai).

---

## What this is

- **Tutorials** — end-to-end walkthroughs, each self-contained, each runnable
- **Example projects** — complete agents you can clone and adapt, not fragments
- **Reference code** — patterns for recurring problems: tool design, evaluation, deployment, observability, human handover
- **Workshop material** — slides, exercises, and solutions from community sessions and conferences

## What this is not

- **Not the product documentation.** The canonical reference is [rasa.com/docs](https://rasa.com/docs/). This repository is educational material.
- **Not the Rasa framework itself.** Rasa Pro is commercial. Running these resources requires a licence key (free for developers — see Requirements).
- **Not a support channel.** Product issues belong with Rasa support or the product repositories. Questions about material here belong in [Discussions](../../discussions/) or in the [community](https://info.rasa.com/community).

---

## Featured resources

| Resource | Persona | Domain | Path |
|---|---|---|---|
| Atlas voice travel agent | Atlas | Horizon Travel | [`examples/mantle-voice-agent`](examples/mantle-voice-agent) |
| Rasano voice banking | Rasano | Retail banking | [`examples/mantle-voice-banking-skills`](examples/mantle-voice-banking-skills) |
| Telano voice telecom care | Telano | Telecom | [`examples/mantle-voice-telco-skills`](examples/mantle-voice-telco-skills) |
| Poly voice insurance | Poly | Insurance | [`examples/mantle-voice-insurance-skills`](examples/mantle-voice-insurance-skills) |
| Schedora voice appointments | Schedora | Clinic booking | [`examples/mantle-voice-appointment-skills`](examples/mantle-voice-appointment-skills) |
| Autono voice car purchase | Autono | Auto retail | [`examples/mantle-voice-car-purchase-skills`](examples/mantle-voice-car-purchase-skills) |
| Atlas voice tutorial tree | Atlas | Horizon Travel | [`tutorials/rasa-voice-agent-tutorial`](tutorials/rasa-voice-agent-tutorial) |

Full catalogs (including empty areas accepting contributions) live in each category README below.

---

## Repository map

The repository holds two kinds of material under two different promises.

**Maintained catalog** — one shared Rasa Pro pin, migrated together, expected to
stay green for as long as it is checked in. Contributed work lives here too:
an example pinned to a release the catalog has moved off is one nobody clones.

| Path | What it holds | Catalog |
|---|---|---|
| [`tutorials/`](tutorials/) | Step-by-step walkthroughs with runnable code | [tutorials/README.md](tutorials/README.md) |
| [`examples/`](examples/) | Complete clone-and-run agents | [examples/README.md](examples/README.md) |
| [`patterns/`](patterns/) | Small reference implementations of recurring problems | [patterns/README.md](patterns/README.md) — accepting contributions |
| [`workshops/`](workshops/) | Slides, exercises, and solutions from sessions | [workshops/README.md](workshops/README.md) — accepting contributions |
| [`snippets/`](snippets/) | Short pieces too small to be a pattern | [snippets/README.md](snippets/README.md) — accepting contributions |
| [`community/`](community/) | Resources written by practitioners, credited to their authors | [community/README.md](community/README.md) — accepting contributions |

**Frozen snapshots** — dated cohort records, pinned to the version their authors
verified and not migrated forward. Still required to be reproducible: a real
`uv.lock`, a name, and a date.

| Path | What it holds | Index |
|---|---|---|
| [`heroes/`](heroes/) | Rasa Heroes cohort projects, one directory per wave | [heroes/README.md](heroes/README.md) — accepting waves |

Why the split, and what each tier guarantees: [`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md).

As the repository grows, **category READMEs are the live inventory**. This root page stays a map and a starting point — not a list of every subdirectory.

---

## How to read a resource

Every resource directory opens its `README.md` with a block like this:

```text
Author:        Rod Rivera
Assessed on:   2026-08-13
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.19.0.dev7, Python 3.11+, uv
Audience:      Practitioners building voice agents with Rasa Skills
Time:          75–90 minutes
```

Read **Assessed on** first. If it is more than six months old, the pin has likely moved. Open an issue if something no longer runs. Material that cannot be re-verified is archived rather than left implying it still works.

Multiple authors are listed comma-separated on the `Author` line. Credit is permanent — see [MAINTAINERS.md](MAINTAINERS.md).

---

## Requirements

Resources here typically assume:

- Python 3.11 or later (see each resource’s `Verified with` line)
- [uv](https://docs.astral.sh/uv/) for dependency management
- A `RASA_LICENSE` key — the [Developer Edition](https://rasa.com/rasa-pro-developer-edition-license-key-request/) key is free
- An LLM provider key, typically `OPENAI_API_KEY`
- For voice examples: a `DEEPGRAM_API_KEY`

Individual resources state any additional requirements.

---

## Validating the catalog

Correctness here is checked by running a command, not by reading the tree. From
the repository root:

```bash
make validate        # ~2s, offline, no uv needed — run before every commit
make ci              # + install every resource and run validate_project
make validate-full   # + rasa train everywhere (needs RASA_LICENSE)
```

`make validate` unit-tests the tooling, then lints both tiers: version and
lockfile consistency, skill authoring rules, resource metadata, committed
secrets, and — for frozen snapshots — that each one's pin, lock, and
`Verified with:` line agree. The same target runs in CI on every pull request
and weekly. What each check enforces — and how to fix a failure — is in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

---

## Keeping resources on the latest Rasa Pro

Every resource in the **maintained catalog** — including everything under
`community/` — pins the same Rasa Pro version, recorded in
[`RASA_PRO_VERSION`](RASA_PRO_VERSION). Only frozen wave projects under
`heroes/` are left out, and [`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md) explains
why. From the repository root:

```bash
make status        # detect pin / lock / README drift
make outdated      # check PyPI for a newer rasa-pro release
make migrate       # rewrite pins, docs, and uv.lock files
make check-all     # sync + assert version + validate_project
make test-all      # also rasa train when RASA_LICENSE is available
```

Override the target with `make migrate VERSION=3.19.0.dev7`, preview it first with
`make migrate-dry VERSION=3.19.0.dev7`, or jump to the newest stable release with
`make latest`. Full maintainer and local-user notes:
[`docs/MIGRATING.md`](docs/MIGRATING.md).

Frozen material has its own two commands — `make snapshots` to see what is
frozen and at which pin, `make check-snapshots` to install each one against the
pin it carries.

---

## Contributing

Contributions are welcome. Contributors are credited by name on the resources they write.

The three things that matter most:

1. **One resource per pull request**
2. **It has to run** — with versions and an assessment date in the README
3. **Write for peers** — including what breaks

If your resource is not the canonical answer to its problem — a provider swap, a
deployment shape, a specific integration — contribute it to
[`community/`](community/). It is maintained on the catalog pin like everything
else, so it does not go stale; migration is the maintainers' job, and whoever
bumps it re-runs it and puts their own name on `Assessed by`. `Author` stays
yours permanently.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for folder choice, the resource template, and the PR checklist. Review ownership and response times are in [MAINTAINERS.md](MAINTAINERS.md). Everyone participates under the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Going further

- **[Rasa University](https://rasa.com/university/)** — structured courses and Developer Certification
- **[rasa.community](https://rasa.community/)** — community hub, heroes programme, and educational library
- **[`heroes/`](heroes/)** — what each Rasa Heroes cohort actually built, wave by wave
- **[rasa.com/docs](https://rasa.com/docs/)** — product documentation

---

## Maintainers

Editorial direction and day-to-day stewardship of this catalog are led by **[Rod Rivera](https://profrod.ai/)** (DevRel at Rasa), with area ownership open to practitioners who contribute and stay. The goal is a multi-author commons: resources name their authors, area owners review their folders, and credit is never stripped.

Full ownership tables, review standards, and succession notes: [MAINTAINERS.md](MAINTAINERS.md).

Security reports: [SECURITY.md](SECURITY.md) — do not open a public issue.

## Licence

The tutorials, examples, and reference code in this repository are released under the Apache License 2.0 — see [LICENSE](LICENSE). That licence covers the teaching material here only. Rasa Pro is a commercial framework under its own terms.
