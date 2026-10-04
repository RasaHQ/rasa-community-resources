# Cedar Clinic with rasa

```text
Author:        Rasa Community
Assessed on:   2026-10-04
Assessed by:   Codex (tutorial source and publication-boundary review)
Verified with: Python 3.12; uv.lock pins rasa-pro 3.21.0.dev5
```

Rasa Pro Mantle declares the send prerequisites and confirmation in skill configuration. Tools write the protected identity and selected medicine into memory.
The tools share the fictional Cedar Clinic records and send a request for
clinical review only after identity, selection and confirmation checks.

## Run locally

Keep this project's `pyproject.toml` and `uv.lock` together. Install its
isolated dependencies with `make install`, copy `.env.example` to a local
`.env` using `make env`, and fill the required provider credentials locally.
The Rasa Pro runtime requires a Rasa Pro licence. Run `make train` before starting the agent.

```sh
make test
make run
# In another terminal:
make web
```

Ask for the fictional caller's prescription refill, then confirm or decline
the read-back. Review the tool policy and offline tests before changing the
confirmation path. `fix.diff` provides an optional playback-boundary variant;
keep variant source and its local output separate.

Shared fictional caller inputs and reproduction commands live in
`../shared/spec/`. Set `--results-root` to a local output folder for scripted
calls. Provider calls are billed. Captured evaluations and logs are not
part of this public tutorial source.

Create and retire isolated experiments using the root workspace tool. Keep
source, dependency locks, fixtures and local outputs when retiring an unused
environment.
