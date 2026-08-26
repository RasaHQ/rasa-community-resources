# Migrating resources to a new Rasa Pro version

This repository pins **one** Rasa Pro version for every clone-and-run resource.
The pin lives in [`RASA_PRO_VERSION`](../RASA_PRO_VERSION) at the repo root.
Each project still has its own `pyproject.toml` + `uv.lock`; the root tooling
keeps those files and the README metadata in sync.

## Which release line to target

> **Do not bump this catalog to the newest stable `rasa-pro` just because it is
> newest.** Every resource here is built on the Mantle / Skills engine, which
> is imported as `rasa.calm_v2`:
>
> ```python
> from rasa.calm_v2.tools.decorator import tool, ToolContext
> from rasa.calm_v2.tools.result import ToolResult
> from rasa.calm_v2.validation import validate_project
> ```
>
> That package ships **only on the `3.19.0.devN` pre-release line**. The stable
> `3.19.x` line (`3.19.0`, `3.19.1`, …) does **not** contain `rasa.calm_v2` at
> all, and the two lines are published in parallel — `3.19.0.dev7` and `3.19.1`
> both landed on 2026-08-25, so "latest on PyPI" resolves to a release that
> cannot run any resource in this repository.
>
> [`RASA_PRO_VERSION_LINE`](../RASA_PRO_VERSION_LINE) encodes this: it holds the
> prefix `3.19.0.dev`, and `make latest` / `make outdated` only consider releases
> on that line. Delete or widen that file once Mantle reaches the stable line.
> To search the whole index anyway:
>
> ```bash
> python scripts/migrate_rasa_pro.py --latest --match ''
> ```
>
> Three guards enforce this, so nothing depends on someone reading this note:
>
> | Guard | When it fires |
> | --- | --- |
> | `make outdated` | Reports the newest release **overall**, not just the newest on the line, and inspects its published wheel for `rasa.calm_v2`. It says whether the release is held back on purpose — or that the line can finally be lifted. |
> | `make migrate VERSION=…` | Refuses **before writing anything** if the target is off-line and its wheel lacks `rasa.calm_v2`. Override with `--allow-missing-engine` only if you mean it. |
> | `make check-all` | Probes `rasa.calm_v2` inside each project venv after a bump and fails loudly if the pinned release does not provide it. |
>
> The first two read the module list straight out of the wheel on PyPI (a ranged
> request for the zip index — a few MB, not the ~100MB wheel), so they track
> what Rasa actually publishes rather than what this file claims.
>
> When `make outdated` reports the module present on a stable release, the
> migration is: delete `RASA_PRO_VERSION_LINE`, run
> `make migrate VERSION=<release>`, then `make ci`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) on `PATH`
- Network access to the index that publishes `rasa-pro` (PyPI by default)
- For `make test-all` / per-project train: a real `RASA_LICENSE`

Credentials are resolved in this order, first hit wins:

1. variables already exported in your shell
2. the project’s own `.env` (from its `.env.example`)
3. a `.env` at the **repository root**

The root file is the convenient one for maintainers: put `RASA_LICENSE`,
`OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` there once and every project picks them
up, instead of copying credentials into all seven. `check-all` prints how many
variables it loaded from it. All `.env` files are gitignored; only `.env.example`
is committed.

## Everyday commands

From the repository root:

```bash
make list          # projects + current pins vs RASA_PRO_VERSION
make status        # exit 1 if anything drifted
make outdated      # ask PyPI whether a newer rasa-pro exists
make migrate       # bump pins, docs, and locks to RASA_PRO_VERSION
make check-all     # sync + assert installed version + validate_project
make test-all      # check-all, then rasa train when a license is present
```

Override the target version for a one-shot bump (also rewrites `RASA_PRO_VERSION`):

```bash
make migrate VERSION=3.19.0.dev7
```

Preview any bump before it touches the working tree — nothing is written and
`uv lock` never runs:

```bash
make migrate-dry VERSION=3.19.0.dev7
```

Jump to the newest release on the supported line (see the box at the top —
constrained by [`RASA_PRO_VERSION_LINE`](../RASA_PRO_VERSION_LINE)):

```bash
make latest
```

Continue past a failing project when you want a full sweep report:

```bash
make check-all KEEP_GOING=1
```

## Stable vs prerelease pins

The pin drives how `uv` is invoked, so the two never fall out of step. When
`RASA_PRO_VERSION` is a dev/rc build (`3.19.0.dev5`, `3.20.0rc1`), the tooling:

- passes `--prerelease=allow` to `uv lock` / `uv sync`
- keeps `[tool.uv] prerelease = "allow"` in every `pyproject.toml`
- writes `uv sync --prerelease=allow` into project Makefiles and install docs

When the pin is stable (`3.19.1`), all three are removed. That matters beyond
tidiness: `--prerelease=allow` applies to the *entire* resolution, so leaving it
on a stable pin quietly lets every other dependency resolve to a prerelease too.

Flipping between the two is handled by `make migrate` in either direction; you
should not need to hand-edit those flags.

## Maintainer workflow (bump everyone)

1. Check what is available:
   ```bash
   make outdated
   ```
2. Preview the bump:
   ```bash
   make migrate-dry VERSION=3.19.0.dev7
   ```
3. Run the migrator. It verifies the version exists on the index *before*
   rewriting anything, then updates every `pyproject.toml` pin and prerelease
   switch, refreshes and re-reads each `uv.lock` to confirm what actually
   resolved, rewrites `Verified with:` / `rasa-pro==…` prose in README/AGENTS
   and the project Makefiles, and finally writes `RASA_PRO_VERSION`:
   ```bash
   make migrate VERSION=3.19.0.dev7
   # or, for the newest release on the supported line:
   make latest
   ```
   `RASA_PRO_VERSION` is written **last**, and only if every project succeeded —
   a failed sweep leaves the pin file untouched so a re-run is a clean retry.
4. Smoke-test:
   ```bash
   make check-all
   ```
5. Optionally train where credentials exist:
   ```bash
   make test-all
   ```
6. Commit the pin file, scripts (if changed), every touched `pyproject.toml` /
   `uv.lock`, and README/AGENTS updates together.

## Local user workflow (old checkout)

If you cloned an older revision and only want your local trees on the current
catalog pin:

```bash
git pull
make migrate      # aligns your working tree with RASA_PRO_VERSION
make check-all
```

Per-resource day-to-day commands (`make install`, `make verify`, `make train`,
…) are unchanged inside each project directory.

## What “in sync” means

`make status` expects, for every discovered project in the **maintained
catalog** — `examples/`, `tutorials/`, `patterns/`, `community/`:

| Location | Must match `RASA_PRO_VERSION` |
|---|---|
| `pyproject.toml` → `rasa-pro==…` | yes |
| `uv.lock` resolved `rasa-pro` version | yes |
| README `Verified with: rasa-pro …` | yes when present |
| Any `rasa-pro==…` / `rasa-pro X.Y.Z` in README or AGENTS | yes |
| `[tool.uv] prerelease` | present only for a prerelease pin |

Drift examples this tooling fixes:

- Install pin still on `dev2` while docs claim `dev3`
- README header bumped but body `rasa-pro==…` left behind
- Lockfile not regenerated after a pin edit
- `prerelease = "allow"` left behind after moving to a stable release

## Troubleshooting

**`uv lock` cannot find the version**  
The release is missing from the configured index, or you need auth. `make
migrate` checks the index up front and refuses to rewrite anything if the target
does not exist, so this usually means a genuine publishing or credentials
problem. Fix index/credentials, then re-run `make migrate` or `make lock-all`.

To bump pins and docs without resolving at all:

```bash
python scripts/migrate_rasa_pro.py --version X.Y.Z --skip-lock
```

To target a version that is not on the index yet (an internal build, say), add
`--no-index-check`.

**The lock resolved a different version than the pin**  
`make migrate` re-reads each `uv.lock` after locking and fails that project if
`rasa-pro` did not resolve to the target. Usually a conflicting constraint
elsewhere in that project's `pyproject.toml`. The pin file is left untouched
when any project fails.

**`validate_project` fails after a bump**  
That is a real product/API break in the resource, not a tooling bug. Fix the
agent files in that project, then re-run `make check-all`.

**`test-all` skips train**  
`RASA_LICENSE` is missing or still a placeholder. `check-all` can still pass;
train is best-effort when credentials exist.

**Nested `tutorial/snippets/**/pyproject.toml`**  
Ignored on purpose. Discovery fixes a depth per root, so only
`examples/<name>/`, `tutorials/<name>/` and `patterns/<name>/` count as
catalog resources.

**`heroes/` wave projects are never migrated**  
Frozen by design. `make migrate` skips them and prints how many it left alone;
targeting one explicitly with `--project` is refused with exit code 2. A cohort
pinned the version it verified, and rewriting that turns a checkable claim into
an untested one.

`community/` **is** migrated along with the rest of the catalog. After the bump,
set `Assessed by:` to whoever ran it, and check for provenance notes the
rewriter may have caught — see [`SNAPSHOTS.md`](SNAPSHOTS.md).

**A resource skipped `rasa train`**  
It declares a provider key in `[tool.rasa-catalog] required-secrets` that this
runner does not have. The skip is loud and names the key. Set it, or accept that
the resource is verified only as far as install and `validate_project`.
`make test-all REQUIRE_SECRETS=1` turns the skip into a hard failure.

## Related docs

- The frozen-snapshot contract: [`SNAPSHOTS.md`](SNAPSHOTS.md)
- Resource metadata template: [`RESOURCE_TEMPLATE.md`](RESOURCE_TEMPLATE.md)
- Contribution rules: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Maintainer review bar: [`../MAINTAINERS.md`](../MAINTAINERS.md)
