# Cedar Clinic with rasa

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-voice-agent-three-frameworks-rasa/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `SPEECHMATICS_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make inspect`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the Inspector starts. In a second terminal, `bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/print-inspector-url.sh"` prints its address.
<!-- codespaces:end -->

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
