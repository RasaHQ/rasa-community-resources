# Frozen snapshots

This repository holds two kinds of material under two different promises. This
page is the contract for the second kind.

---

## The two tiers

| | Maintained catalog | Frozen snapshots |
|---|---|---|
| Where | `tutorials/` `examples/` `patterns/` `workshops/` `snippets/` `community/` | `heroes/` |
| Pinned to | [`RASA_PRO_VERSION`](../RASA_PRO_VERSION), for all of them at once | whatever its author verified |
| `make migrate` | rewrites it | never touches it |
| `version-consistency` lint | enforced | skipped |
| Who keeps it working | the maintainers | nobody, by agreement |
| When it stops working | it is fixed | it is archived, with the reason |

The distinction is a **maintenance promise**, not a topic.

`community/` is maintained. That is deliberate: an example pinned to a release
the rest of the catalog has moved off is one nobody clones, so being current is
most of what makes a contributed resource worth checking in at all. The
contributor is not signed up for that work — `make migrate` is, and the
maintainer who runs it re-stamps `Assessed by`. What a contributor keeps is
authorship, permanently.

`heroes/` is the exception. A wave closes, its participants move on, and what
is left is a dated record of what that cohort built rather than something
anyone has undertaken to keep running.

## Why freeze anything

Two failures this avoids.

**The first:** `make migrate` rewrites every `rasa-pro==` pin and every
`Verified with:` line it touches. Left unattended, that turns a dated, checkable
claim — *"I ran this, on this version, on this date"* — into an assertion the
maintainers made on the author's behalf and never tested. That is worse than a
stale pin, because it reads as verified.

For the maintained tier the answer is not to freeze but to **re-verify and
re-stamp**: whoever migrates a resource runs `make check-all`, puts their own
name on `Assessed by`, and records in the resource README which claims are
theirs and which are the original author's. A resource that cannot be
re-verified — because it needs a provider key nobody has, or because it no
longer runs — is archived, not quietly carried forward.

**The second:** if every past cohort's project must stay green forever, then one
upstream change breaks the build for work that is years old and whose authors
have moved on. The realistic responses are to delete their work or to disable
the check. Freezing is the third option, and it is honest about what is true:
this ran, then, and here is the lock that proves what "then" means.

## What freezing does *not* excuse

A frozen resource is held to everything except the shared pin:

| Check | What it requires |
|---|---|
| `snapshot-pin` | `pyproject.toml`, `uv.lock`, and the README's `Verified with:` line all name the same version — and a `uv.lock` exists at all |
| `index-rows` | the resource is listed in its index (`community/README.md`, or its wave charter) — applies to both tiers |
| `resource-metadata` | `Author:`, `Assessed on:`, `Assessed by:`, `Verified with:`, plus `Kind:` under `community/` and `Wave:` under `heroes/` |
| `env-example` | a `.env.example` so a clean clone can bootstrap |
| `secret-hygiene` | no committed keys, licences, or `.env` |
| `heroes-layout` | wave slugs are `wave-NN-<theme>`; projects live at `<wave>/projects/<project>/` |

A snapshot without a `uv.lock` is not frozen. It is a project with a date
written on it: `uv sync` will resolve it to something the author never ran, and
the claim in its README becomes unfalsifiable. That is why the lock is a hard
requirement rather than a suggestion.

## Running the checks

```bash
make validate           # both tiers; the snapshot checks are part of the gate
make snapshots          # what is frozen, and at which pin
make check-snapshots    # install each frozen resource and run validate_project

python scripts/lint_repo.py --check snapshot-pin --check index-rows
```

## Resources that need a provider key

A resource built on something other than the catalog's default providers
declares the key it needs:

```toml
[tool.rasa-catalog]
required-secrets = ["GEMINI_API_KEY"]
```

`rasa train` is then **skipped with a warning** on any runner that lacks it,
instead of dying on an unexpanded `${GEMINI_API_KEY}` and reading as a broken
resource. `make test-all REQUIRE_SECRETS=1` turns that skip back into a
failure when you want "trained everything" to mean it. The declared key must
also appear in the resource's `.env.example`, which `env-example` enforces —
otherwise `make env` hands a reader a silently incomplete `.env`.

The honest consequence: such a resource is CI-verified as far as *install and
`validate_project`*, and no further, until the key is added to the repository
secrets. Its README should say so rather than implying a full green run.

`make status` and `make migrate` deliberately cover the catalog only. Asking
`list_projects.py --status` for a frozen scope is a usage error rather than a
guess: reporting a frozen project as *drifted* would be a category error, and
reporting it as *clean* would be a lie.

## Migrating a contributed resource

`community/` moves with the rest of the catalog, so this is part of a normal
version bump rather than a special event. What is not automatic is the claim:

1. `make migrate` rewrites the pin, the docs and the lock.
2. `make check-all` proves it still installs and validates at the new version.
3. Set `Assessed by:` to **the person who just ran that**, not the original
   author, and set `Assessed on:` to the date they ran it. `Author:` never
   changes.
4. If the resource carries a provenance table naming who verified what, update
   the maintainer row and leave the author's row alone.

A resource that will not come forward is archived (below) rather than pinned
in place, because a stale pin inside a maintained folder reads as current.

## Promoting a community resource into a category folder

When a contributed resource becomes the canonical treatment of its problem and
someone takes on area ownership:

1. Someone states in an issue that they will own it, and is added to the area
   table in [MAINTAINERS.md](../MAINTAINERS.md).
2. `git mv` the directory into the right category folder. Keep the history.
3. Move its row from `community/README.md` into the category catalog, and leave
   a line behind pointing at where it went.

## Archiving

A resource is archived — not deleted — when it can no longer be made to run at
the current pin, or when its `Assessed on` date is old enough that nobody should
trust it silently. Move it under `archive/`, keep the author's name on it, and
record why in the directory's README. Credit is permanent; the implication that
something still works is not.

For `community/` this is the release valve that lets the folder stay
maintained: nothing is carried forward on a stale pin, so anything still in
`community/` is on the catalog pin and has been verified there.
