# Migrating resources to a new Rasa Pro version

This repository pins **one** Rasa Pro version for every clone-and-run resource.
The pin lives in [`RASA_PRO_VERSION`](../RASA_PRO_VERSION) at the repo root.
Each project still has its own `pyproject.toml` + `uv.lock`; the root tooling
keeps those files and the README metadata in sync.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) on `PATH`
- Network access to the index that hosts `rasa-pro` prereleases
- For `make test-all` / per-project train: a real `RASA_LICENSE` in the
  environment or in each project’s `.env` (from `.env.example`)

## Everyday commands

From the repository root:

```bash
make list          # projects + current pins vs RASA_PRO_VERSION
make status        # exit 1 if anything drifted
make migrate       # bump pins, docs, and locks to RASA_PRO_VERSION
make check-all     # sync + assert installed version + validate_project
make test-all      # check-all, then rasa train when a license is present
```

Override the target version for a one-shot bump (also rewrites `RASA_PRO_VERSION`):

```bash
make migrate VERSION=3.19.0.dev5
```

Continue past a failing project when you want a full sweep report:

```bash
make check-all KEEP_GOING=1
```

## Maintainer workflow (bump everyone)

1. Confirm the new package is publishable (`uv pip index versions rasa-pro` or
   your internal index).
2. Set the pin:
   ```bash
   echo '3.19.0.dev5' > RASA_PRO_VERSION
   # or: make migrate VERSION=3.19.0.dev5
   ```
3. Run the migrator (rewrites every `pyproject.toml`, refreshes `uv.lock`,
   updates `Verified with:` / `rasa-pro==…` prose in README/AGENTS, and the
   example line in the root README):
   ```bash
   make migrate
   ```
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

`make status` expects, for every discovered project under `examples/` and
`tutorials/`:

| Location | Must match `RASA_PRO_VERSION` |
|---|---|
| `pyproject.toml` → `rasa-pro==…` | yes |
| `uv.lock` resolved `rasa-pro` version | yes |
| README `Verified with: rasa-pro …` | yes when present |

Drift examples this tooling fixes:

- Install pin still on `dev2` while docs claim `dev3`
- README header bumped but body `rasa-pro==…` left behind
- Lockfile not regenerated after a pin edit

## Troubleshooting

**`uv lock` cannot find the version**  
The prerelease is missing from the configured index, or you need auth. Fix
index/credentials, then re-run `make migrate` or `make lock-all`. Use
`make migrate …` with `--skip-lock` only when you intentionally want pin/doc
edits without resolving (via
`python scripts/migrate_rasa_pro.py --skip-lock`).

**`validate_project` fails after a bump**  
That is a real product/API break in the resource, not a tooling bug. Fix the
agent files in that project, then re-run `make check-all`.

**`test-all` skips train**  
`RASA_LICENSE` is missing or still a placeholder. `check-all` can still pass;
train is best-effort when credentials exist.

**Nested `tutorial/snippets/**/pyproject.toml`**  
Ignored on purpose. Discovery only considers `examples/<name>/` and
`tutorials/<name>/`.

## Related docs

- Resource metadata template: [`RESOURCE_TEMPLATE.md`](RESOURCE_TEMPLATE.md)
- Contribution rules: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Maintainer review bar: [`../MAINTAINERS.md`](../MAINTAINERS.md)
