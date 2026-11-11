# Fiserv banking demo

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-banking/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, configured by the operator as repository or organisation Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Development build: the shared banking transport and native host interface are
being integrated. This is not a qualified vendor integration or a finished demo.

```text
Author:        Rasa Community contributors
Assessed on:   not yet qualified
Assessed by:   No complete demo qualification run yet
Verified with: Not yet verified as a banking assistant
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
```

The build uses the current catalogue pin under an explicit baseline ruling.
Rasa Pro 3.22 promotion still needs the normal release qualification; it has
not been silently adopted here.

## Start and test

Open this project’s Codespaces configuration and run
`make run`. Inspector uses private forwarded port 5005. PR CI runs `make test`
with no licence, model or speech keys. The final real spoken check belongs to
the operator after the browser path and text controls are ready.

The operator supplies Codespaces secrets named `RASA_PRO_LICENSE`,
`OPENAI_API_KEY` and `DEEPGRAM_API_KEY`. Values never belong in this repository,
logs or screenshots. A licence does not pay for model or speech services.
Only fictional information may be spoken. The provider receives live audio;
both speech request builders set `mip_opt_out=true`. Local tests inspect the
constructed requests without sending audio. This opt-out is not zero retention.

## Banking boundary

The `fiserv` configuration consumes the same `banking-demo-shared` package
as the other example. No vendor client, mock or guard is copied here. The simulator uses our own banking contract and fictional accounts.

Mocks follow the shared banking contract; vendor mappings are illustrative, based on public documentation, and not tested against vendor systems.

No protected read or write trusts a model-provided identity or verification
flag. A transfer needs the trusted host interface, unchanged canonical review
and deterministic confirmation. Missing host proof refuses. Unknown dispatch
outcomes are not automatically retried; queued is not posted.

The native text controls exercise actual archived Rasa turns and loopback MCP,
with a scripted model. They do not establish real bank identity, vendor
conformance or a completed browser voice check.

The simulator keeps reviews and outcomes only in memory. An unknown result blocks
new transfers for that fictional caller until the teaching host stops. Restarting
clears this mock state; it does not reconcile a payment. There is no real bank
state behind these examples. Never use a restart as a retry strategy for a real
transfer.
