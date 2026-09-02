# wave-01-mantle projects

Nothing has landed here yet. Each participant project in this wave is one
directory at this level:

```text
heroes/wave-01-mantle/projects/<your-handle>-<project-slug>/
  README.md          metadata block: Author, Wave, Assessed on, Assessed by, Verified with
  pyproject.toml     pins the rasa-pro version you verified against
  uv.lock            committed, and matching that pin
  .env.example       no secrets, only the key names your project needs
  …
```

Add your project's row to the [wave charter](../README.md) in the same pull
request that adds the directory. A directory with no row fails `make validate`,
because an unlisted project is one nobody can find.

Full contract for a frozen wave project: [`docs/SNAPSHOTS.md`](../../../docs/SNAPSHOTS.md).

This file exists only so the empty `projects/` directory can be committed
before the first project arrives; it is not itself a project and no check
discovers it.
