# Workspaces and isolated environments

Create each development worktree through Git:

```sh
python3 scripts/workspace.py worktree ../rcr-my-experiment my-experiment
```

Git checks out source without copying the current checkout's environments,
dependencies, caches or build outputs. Avoid copying whole checkouts with
`cp -R` or unrestricted `rsync`. For committed-source exports, use
`python3 scripts/workspace.py snapshot source.tar`. Preserve unfinished work
separately with bundles, indexes, binary diffs and unique source or assets.
Ignored recordings, results, datasets and credentials can still be necessary.

Install only the project you plan to run:

```sh
make environment PROJECT=examples/mantle-voice-agent EXPERIMENT=atlas-test
```

This runs `uv sync --locked` against that project's manifest and lock. It
records the experiment owner and installed-file hashes inside the environment.
An existing environment is retained until its owner has finished with it.
Different framework versions and experiments keep their own environments.
An editorial worktree needs no Python environment unless it runs a tutorial.

After the experiment and its jobs finish:

```sh
python3 scripts/workspace.py retire examples/mantle-voice-agent \
  --owner atlas-test --inactive
```

Retirement checks ownership, the installed files and the rebuild inputs. It
refuses changed, copied or unmanaged environments; preserve and audit those
before cleanup. The retirement receipt stays beside the manifest, outside the
deleted environment. Rebuild with `uv sync --locked --project <project>`.
Keep all source, manifests, locks, results, recordings and model receipts.

Root `install-all`, `check-all`, `check-snapshots`, `test-all` and `verify-all`
create environments across the catalog. They require `ALL_PROJECTS=1` when
called directly. Explicit `make ci` and `make validate-full` retain their full
catalog checks. Run those in a designated verification workspace, using the
host's existing coordination mechanism, then retire unused environments when
verification is complete. `make validate` is the offline development gate.
