# Contributing

Thank you for helping grow this catalog. This repository is community teaching
material for practitioners building and operating agents with Rasa. Contributions
are credited by name on the resources they touch and stay credited.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## What belongs here

| Folder | Put it here when… |
|---|---|
| [`examples/`](examples/) | You have a **complete, clone-and-run** agent others can adapt |
| [`tutorials/`](tutorials/) | You have a **step-by-step walkthrough** with runnable code (and usually paste-ready snippets) |
| [`patterns/`](patterns/) | You have a **small, focused** reference for one recurring problem (tool design, handoff, eval, etc.) |
| [`workshops/`](workshops/) | You have **slides, exercises, and solutions** from a session |
| [`snippets/`](snippets/) | You have something useful that is **too small** to be a pattern |

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
6. Pin `rasa-pro` to the version in [`RASA_PRO_VERSION`](RASA_PRO_VERSION).
   After adding a resource, run `make status` from the repo root. When bumping
   Rasa Pro across the catalog, use `make migrate` then `make check-all`
   (see [docs/MIGRATING.md](docs/MIGRATING.md)).

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

---

## Validating your change

Run this before opening a pull request. It is offline, needs no `uv` and no
virtualenv, and takes about two seconds:

```bash
make validate
```

It runs the tooling unit tests, lints the whole catalog (version consistency,
lockfile sync, skill authoring rules, resource metadata, committed secrets), and
fails on pin drift. CI runs the same target, so a green `make validate` locally
means a green gate on the PR.

If you changed a runnable resource, also install and validate it for real:

```bash
make ci                      # every project: install + validate_project
make check-all KEEP_GOING=1  # same, but report all failures instead of stopping
```

`make validate-full` additionally trains every agent, which needs a real
`RASA_LICENSE`. See [`docs/VALIDATION.md`](docs/VALIDATION.md) for what each
check enforces and how to fix a failure.

## Pull request checklist

- [ ] One resource only
- [ ] `make validate` passes
- [ ] README includes the metadata block above
- [ ] Verified on a clean environment; `Assessed on` / `Verified with` are current
- [ ] Category README catalog updated with a new row
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
