# Rasa Community Resources

**New: the Rasa Travel Agent Factory masterclass.** [Start here: credentials, Codespaces and your first live result](workshops/software-factories-masterclass/README.md) · [Teaching deck](workshops/software-factories-masterclass/slides/masterclass-slides.pdf) · [Instructor card](workshops/software-factories-masterclass/FACILITATOR.md) · [Printed setup sheet (PDF)](workshops/software-factories-masterclass/handout/rasa-travel-workshop-one-pager.pdf) · [Join the Rasa Community](https://rasa.community/join/)

Choose what you want to do:

- **Learn at your own pace:** [Build your first Mantle agent](https://rasa.community/library/tutorials/mantle-starter-pack/) with a self-paced tutorial and a runnable companion.
- **Join the live workshop:** [Open the Rasa Travel Agent Factory Codespace](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/travel-factory/devcontainer.json) to speak to a Mantle travel agent and review agents that Codex and a hosted OpenAI Agents session build. It needs your own Rasa, OpenAI and Deepgram keys. [First time? Follow the step-by-step guide.](workshops/software-factories-masterclass/README.md)
- **Run a finished agent:** [Start with the Atlas voice agent](examples/mantle-voice-agent/README.md) to try a complete travel assistant before adapting it.
- **Find a reusable pattern:** [Browse patterns](patterns/README.md) for focused implementations you can bring into an existing agent.
- **Contribute a resource:** [Read the contribution guide](CONTRIBUTING.md) to choose a folder, check your example, and keep its authors credited.

This is the code companion to [rasa.community](https://rasa.community/). Tutorials, examples, and reference code live in their own folders, with setup instructions and the versions they were tested against. For the presenter-led Software Factories workshop, follow the [workshop guide](workshops/software-factories-masterclass/README.md). It needs no local installation; the hosted builds use your own OpenAI key and can incur charges.

## Browse the repository

Use the category catalogs below when you already know what you need. For isolated local development, read [workspaces and environments](docs/WORKSPACES.md) before installing a resource.

## What this is

- **Tutorials**—end-to-end walkthroughs, each self-contained, each runnable
- **Example projects**—complete agents you can clone and adapt, not fragments
- **Reference code**—patterns for recurring problems: tool design, evaluation, deployment, observability, human handover
- **Workshop material**—slides, exercises, and solutions from community sessions and conferences

## What this is not

- **Not the product documentation.** The canonical reference is [rasa.com/docs](https://rasa.com/docs/). This repository is educational material.
- **Not the Rasa framework itself.** Rasa Pro is commercial. Running these resources requires a license key (free for developers—see Requirements).
- **Not a support channel.** Product issues belong with Rasa support or the product repositories. Questions about material here belong in the [community](https://info.rasa.com/community).

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
| Vela voice banking (Rime text-to-speech (TTS)) | Vela | Retail banking | [`examples/mantle-voice-rime-skills`](examples/mantle-voice-rime-skills) |
| Vela voice banking (Speechmatics automatic speech recognition (ASR)) | Vela | Retail banking | [`examples/mantle-voice-speechmatics-skills`](examples/mantle-voice-speechmatics-skills) |
| Atlas voice tutorial tree | Atlas | Horizon Travel | [`tutorials/rasa-voice-agent-tutorial`](tutorials/rasa-voice-agent-tutorial) |
| Voice vendor router (ASR/TTS failover and vendor swapping) |—| Voice infrastructure | [`patterns/voice-vendor-router`](patterns/voice-vendor-router) |

Full catalogs (including empty areas accepting contributions) live in each category README below.

---

## Repository map

The repository holds two kinds of material under two different promises.

**Maintained catalog**—one shared Rasa Pro pin, migrated together, expected to
stay green for as long as it is checked in. Contributed work lives here too:
an example pinned to a release the catalog has moved off is one nobody clones.

| Path | What it holds | Catalog |
|---|---|---|
| [`tutorials/`](tutorials/) | Step-by-step walkthroughs with runnable code | [tutorials/README.md](tutorials/README.md) |
| [`examples/`](examples/) | Complete clone-and-run agents | [examples/README.md](examples/README.md) |
| [`patterns/`](patterns/) | Small reference implementations of recurring problems | [patterns/README.md](patterns/README.md)—accepting contributions |
| [`workshops/`](workshops/) | Slides, exercises, and solutions from sessions | [workshops/README.md](workshops/README.md)—accepting contributions |
| [`snippets/`](snippets/) | Short pieces too small to be a pattern | [snippets/README.md](snippets/README.md)—accepting contributions |
| [`community/`](community/) | Resources written by practitioners, credited to their authors | [community/README.md](community/README.md)—accepting contributions |

**Frozen snapshots**—dated cohort records, pinned to the version their authors
verified and not migrated forward. Still required to be reproducible: a real
`uv.lock`, a name, and a date.

| Path | What it holds | Index |
|---|---|---|
| [`heroes/`](heroes/) | Rasa Heroes cohort projects, one directory per wave | [heroes/README.md](heroes/README.md)—accepting waves |

Why the split, and what each tier guarantees: [`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md).

As the repository grows, **category READMEs are the live inventory**. This root page stays a map and a starting point—not a list of every subdirectory.

---

## How to read a resource

Every resource directory opens its `README.md` with a block like this:

```text
Author:        Rod Rivera
Assessed on:   2026-08-13
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.21.0.dev5, Python 3.11+, uv
Audience:      Practitioners building voice agents with Rasa Skills
Time:          75–90 minutes
```

Read **Assessed on** first. If it is more than six months old, the pin has likely moved. Open an issue if something no longer runs. Material that cannot be re-verified is archived rather than left implying it still works.

Multiple authors are listed comma-separated on the `Author` line. Credit is permanent—see [MAINTAINERS.md](MAINTAINERS.md).

---

## Requirements

Resources here typically assume:

- Python 3.11 or later (see each resource’s `Verified with` line)
- [uv](https://docs.astral.sh/uv/) for dependency management
- A `RASA_LICENSE` key—the [Developer Edition](https://rasa.community/license/) key is free
- A large language model (LLM) provider key, typically `OPENAI_API_KEY`
- For voice examples: a `DEEPGRAM_API_KEY`

Individual resources state any additional requirements.

---

## Run any resource in a GitHub Codespace

Every example, tutorial, pattern and community resource opens in its own Codespace with its locked dependencies installed, and its README starts with an **Open in GitHub Codespaces** button. Nothing needs installing on your laptop.

1. Get a free [Rasa Developer Edition license](https://rasa.community/#request-license) and the provider key your resource names (OpenAI, Anthropic, Gemini, Deepgram and so on).
2. Open [GitHub → Settings → Codespaces](https://github.com/settings/codespaces), choose **New secret**, and save each value under the exact name the resource's README lists, such as `RASA_LICENSE` or `OPENAI_API_KEY`. Under **Repository access**, pick `RasaHQ/rasa-community-resources`. You do this once; every resource reuses the secrets.
3. Click the resource's **Open in GitHub Codespaces** button, choose **Create codespace**, and wait for the install to finish.
4. Run the first command in the README. It checks the install without calling a model.

Use each resource's own button, not the Codespaces picker: the picker lists every configuration in this repository, and only the button opens the right one. The one exception is the Software Factories masterclass, which has its own guide.

**What the SSH feature changes.** Each configuration adds the dev container `sshd` feature (pinned to version 1.1.0) so that maintainers and instructors can check a Codespace with `gh codespace ssh`. It installs the OpenSSH server and client and `lsof`, creates an SSH group, edits the PAM configuration, sets `PermitRootLogin yes` in the SSH server configuration, and starts the server on port 2222 from an entrypoint script. No port is forwarded for it, no password is set by default, and reaching it needs `gh codespace ssh` with your own GitHub sign-in through GitHub's tunnel. This is the published feature's documented behaviour, not something these configurations test. It affects only the Codespace, never your laptop.

If you add or fix a secret after the Codespace exists, stop and reopen that Codespace so it picks the secret up. The configurations are generated by `python3 scripts/generate_codespaces.py` from each resource's own files; do not edit them by hand.

## Validating the catalog

Correctness here is checked by running a command, not by reading the tree. From
the repository root:

```bash
make validate        # ~2s, offline, no uv needed—run before every commit
make ci              # + install every resource and run validate_project
make validate-full   # + rasa train everywhere (needs RASA_LICENSE)
```

`make validate` unit-tests the tooling, then lints both tiers: version and
lockfile consistency, skill authoring rules, resource metadata, committed
secrets, and—for frozen snapshots—that each one's pin, lock, and
`Verified with:` line agree. The same target runs in continuous integration (CI) on every pull request
and weekly. What each check enforces—and how to fix a failure—is in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

---

## Keeping resources on the latest Rasa Pro

Every resource in the **maintained catalog**—including everything under
`community/`—pins the same Rasa Pro version, recorded in
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

Override the target with `make migrate VERSION=3.21.0.dev5`, preview it first with
`make migrate-dry VERSION=3.21.0.dev5`, or jump to the newest stable release with
`make latest`. Full maintainer and local-user notes:
[`docs/MIGRATING.md`](docs/MIGRATING.md).

Frozen material has its own two commands—`make snapshots` to see what is
frozen and at which pin, `make check-snapshots` to install each one against the
pin it carries.

---

## Contributing

Contributions are welcome. Contributors are credited by name on the resources they write.

The three things that matter most:

1. **One resource per pull request**
2. **It has to run**—with versions and an assessment date in the README
3. **Write for peers**—including what breaks

If your resource is not the canonical answer to its problem—a provider swap, a
deployment shape, a specific integration—contribute it to
[`community/`](community/). It is maintained on the catalog pin like everything
else, so it does not go stale. Migration is the maintainers' job, and whoever
bumps it re-runs it and puts their own name on `Assessed by`. `Author` stays
yours permanently.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for folder choice, the resource template, and the PR checklist. Review ownership and response times are in [MAINTAINERS.md](MAINTAINERS.md). Everyone participates under the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Going further

- **[Rasa University](https://rasa.com/university/)**—structured courses and Developer Certification
- **[rasa.community](https://rasa.community/)**—community hub, heroes program, and educational library
- **[`heroes/`](heroes/)**—what each Rasa Heroes cohort actually built, wave by wave
- **[rasa.com/docs](https://rasa.com/docs/)**—product documentation

---

## Maintainers

Editorial direction and day-to-day stewardship of this catalog are led by **[Rod Rivera](https://profrod.ai/)** (developer relations at Rasa), with area ownership open to practitioners who contribute and stay. The goal is a multi-author commons: resources name their authors, area owners review their folders, and credit is never stripped.

Full ownership tables, review standards, and succession notes: [MAINTAINERS.md](MAINTAINERS.md).

Security reports: [SECURITY.md](SECURITY.md)—do not open a public issue.

## License

The tutorials, examples, and reference code in this repository are released under the Apache License 2.0—see [LICENSE](LICENSE). That license covers the teaching material here only. Rasa Pro is a commercial framework under its own terms.
