# Contributing

Thank you for helping grow this catalog. This repository is community teaching
material for practitioners building and operating agents with Rasa. Contributions
are credited by name on the resources they touch and stay credited.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Where contributed work goes

Almost everything here is **maintained**: it pins the shared version in
[`RASA_PRO_VERSION`](RASA_PRO_VERSION), moves forward with `make migrate`, and
is expected to keep running. That includes [`community/`](community/) — a
resource pinned to a release the catalog has left behind is one nobody clones,
so being current is most of what makes it useful.

You are not signing up for that maintenance by contributing. Migration is the
maintainers' job, and whoever bumps your resource re-runs it and puts **their**
name on `Assessed by:` — never yours on a version you did not test. `Author:` is
yours permanently.

The one frozen exception is [`heroes/`](heroes/): a Rasa Heroes wave is a dated
record of what a cohort built, its participants move on, and nobody undertakes
to keep it running against future releases. Full contract:
[`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md).

If a resource can no longer be brought forward, it is archived with the reason
rather than left on a stale pin implying it still runs.

## What belongs where

| Folder | Put it here when… |
|---|---|
| [`examples/`](examples/) | You have a **complete, clone-and-run** agent others can adapt |
| [`tutorials/`](tutorials/) | You have a **step-by-step walkthrough** with runnable code (and usually paste-ready snippets) |
| [`patterns/`](patterns/) | You have a **small, focused** reference for one recurring problem (tool design, handoff, eval, etc.) |
| [`workshops/`](workshops/) | You have **slides, exercises, and solutions** from a session |
| [`snippets/`](snippets/) | You have something useful that is **too small** to be a pattern |
| [`community/`](community/) | Any of the above, credited to you, without having to claim it is the canonical answer — see [community/README.md](community/README.md) |
| [`heroes/`](heroes/) | It is a **Rasa Heroes wave deliverable**; it belongs to its cohort — see [heroes/README.md](heroes/README.md) |

If you are unsure, open an issue before a large PR. Out-of-scope work is declined
with a pointer to a better home when we can offer one.

Showcase projects that are not teaching material belong in the
[community showcase](https://rasa.community/showcase/) via the
[community application](https://info.rasa.com/community/), not as a PR here.

---

## The three rules that matter most

1. **One resource per pull request.** A tutorial, an example, a pattern, a
   workshop pack, or a snippet — not a mix.
2. **It has to run.** State the versions you verified against and the date you
   verified them in the resource README. A contribution that works only on your
   machine is a maintenance liability.
3. **Write for peers.** The reader is a working practitioner. Do not over-explain
   the basics and do not skip failure modes. If something breaks in production,
   say what breaks and why.

Full review standards and response expectations live in [MAINTAINERS.md](MAINTAINERS.md).

---

## Before you open a PR

1. Pick the correct top-level folder (table above).
2. Copy [docs/RESOURCE_TEMPLATE.md](docs/RESOURCE_TEMPLATE.md) into your
   resource’s `README.md` and fill every metadata field.
3. Follow the naming and layout notes in that category’s README
   ([examples](examples/README.md), [tutorials](tutorials/README.md),
   [patterns](patterns/README.md), [workshops](workshops/README.md),
   [snippets](snippets/README.md)).
4. Add one row to the category README catalog when your resource lands.
5. Keep secrets out of git — `.env.example` only; never commit keys.
6. Pin `rasa-pro` to the version in
   [`RASA_PRO_VERSION`](RASA_PRO_VERSION) and commit a `uv.lock` alongside it
   (`uv lock` in your resource directory). The lock is not optional — without
   it `uv sync` resolves to something you never ran, and the claim in your
   README stops being checkable. After adding a resource, run `make status`.
   (A `heroes/` wave project instead pins whatever version *you* verified; it
   is never migrated.)

7. If your resource needs a provider key beyond `RASA_LICENSE`,
   `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`, declare it — otherwise `rasa train`
   dies on an unexpanded variable and reads as a broken project:

   ```toml
   [tool.rasa-catalog]
   required-secrets = ["GEMINI_API_KEY"]
   ```

   List it in your `.env.example` too; `make validate` checks that.

### Metadata block (required)

Every resource README opens with:

```text
Author:        Your Name
Assessed on:   YYYY-MM-DD
Assessed by:   Name who last verified it runs
Verified with: rasa-pro X.Y.Z, Python 3.11+, uv
Audience:      Who this is for (one line)
Time:          Honest estimate to complete or explore
```

Multiple authors are listed on one line, comma-separated
(`Author: Alice Chen, Rod Rivera`). Substantive later edits add a co-author
rather than replacing the original name. See the attribution policy in
[MAINTAINERS.md](MAINTAINERS.md).

Two folders add one field, because neither is typed by its path:

- under `community/` — `Kind: pattern | example | tutorial | workshop | snippet`
- under `heroes/` — `Wave: wave-NN-<theme>`

When recording a version you verified **in the past** — a provenance note, a
changelog line — write it as a bare backticked version like `` `3.19.0.dev5` ``,
never as the words `rasa-pro` followed by that number. `make migrate` rewrites
the second form, which silently turns your record of what you tested into a
claim about a version you did not.

This is not theoretical, and the linter enforces it: the sentence you are
reading originally spelled out the bad form as an example, and
`version-consistency` failed the build for it.

---

## Validating your change

Run this before opening a pull request. It is offline, needs no `uv` and no
virtualenv, and takes about two seconds:

```bash
make validate
```

It runs the tooling unit tests, lints both tiers (version consistency, lockfile
sync, skill authoring rules, resource metadata, committed secrets, and — for
frozen snapshots — that the pin, the lock and the README agree), and fails on
pin drift. CI runs the same target, so a green `make validate` locally means a
green gate on the PR.

If you changed a runnable resource, also install and validate it for real:

```bash
make ci                      # every project: install + validate_project
make check-all KEEP_GOING=1  # same, but report all failures instead of stopping
```

If you contributed a frozen snapshot, prove it installs at its own pin:

```bash
make check-snapshots
```

`make validate-full` additionally trains every agent in the maintained catalog,
which needs a real `RASA_LICENSE`. See [`docs/VALIDATION.md`](docs/VALIDATION.md)
for what each check enforces and how to fix a failure.

## Pull request checklist

- [ ] One resource only
- [ ] `make validate` passes
- [ ] README includes the metadata block above
- [ ] Verified on a clean environment; `Assessed on` / `Verified with` are current
- [ ] `uv.lock` committed and resolving to the version the README claims
- [ ] Category README catalog (or, for a wave project, the wave charter) updated with a new row
- [ ] No secrets, licence keys, or personal data in the tree
- [ ] Failure modes or operational caveats stated where relevant
- [ ] You agree to the [Code of Conduct](CODE_OF_CONDUCT.md)

---

## Becoming an area owner

Contribute two accepted resources in the same area, then open an issue proposing
yourself. Area owners and review SLAs are listed in [MAINTAINERS.md](MAINTAINERS.md).

---

## Security

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).
