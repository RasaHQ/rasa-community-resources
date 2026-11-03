# Jacaranda Bank conversation with a Jev account selector

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-jev-with-rasa-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Start with [the full walkthrough](../README.md). This project keeps Mantle's
ordinary orchestrator and calls a bounded local Laya or optional hosted Jev worker through decorated tools.
The account choices and transaction rows are fictional. Public demo labels do
not authenticate a customer.

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Scripted TypeSafe SDK controls and decorated Mantle tool bindings
**Verified with:** Rasa Pro 3.21.0.dev5, typesafe-sdk 0.7.4 and Python 3.12.13.
The initial offline run passed 22 controls; the cold-archive control needs
licensed training first. Jev responses were scripted through the actual SDK.

Run `make install`, `make demo` and `make test` here. `make worker` serves scripted
SDK responses; `make worker-local` uses the separately running pinned Laya model; `make worker-live` requires `TYPESAFE_API_KEY` and sends paid Jev
requests. `make train` requires an issued Rasa licence and `OPENAI_API_KEY`;
`make run` serves the REST conversation on loopback port 5030. Keep the selected
worker running on loopback port 5029. `.env.example` lists the variable names.

The tests check TypeSafe request/response wiring, account membership and revision
checks, sender binding, unavailable services and the loaded trained archive.
The archive test skips until you run training. Qualify actual model selection
and conversation behaviour separately with your own requests. Retain both
projects' locks, and create an environment only for the project you run.
