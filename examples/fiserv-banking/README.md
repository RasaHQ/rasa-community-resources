# Fiserv banking demo

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-banking/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, configured by the operator as repository or organisation Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Development build: native text controls exercise all eight shared banking
actions. Independent source review and the final spoken browser check remain
open. This is not a qualified vendor integration.

```text
Author:        Rasa Community contributors
Assessed on:   11 November 2026, native text controls only
Assessed by:   Automated native conversation and service tests
Verified with: Scripted model, actual archived runtime and local MCP
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
as the other example. No vendor client, mock or guard is copied here. The
simulator uses our own banking contract and fictional accounts.

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

## Try the conversation

Run `make run`, then open the private Inspector URL printed by the launcher.
Type in Inspector first. For speech, use that same page over the forwarded
HTTPS URL, allow the browser's microphone request and speak only fictional data.
The actual browser microphone and playback check is still pending.

The following values are authored mock data, including the historical dates.
They are not current bank balances, payment dates or financial quotes.

| Ask | Expected service result |
|---|---|
| List my accounts. | `checking-A`, `savings-A` and `loan-A` only |
| What is my checking balance? | Available balance USD 200.00 |
| What is my checking ledger balance? | Ledger balance USD 220.00 |
| Show my checking history, then the next page. | One entry per page; the second page is the last |
| What is my next loan payment? | USD 75.00, due 20 January 2026 |
| Give me the supplied loan payoff for 15 January 2026. | USD 650.50 for that date |
| Give me a payoff for 16 January 2026. | Unsupported; no calculated substitute |
| Move USD 10 from my checking to my savings. | Canonical review only; no submission yet |
| Confirm transfer. | `accepted`; this does not mean posted |

For a refusal check, request another review, say “No, do not transfer”, then say
“Confirm transfer.” The canceled review must not submit. A question between the
review and confirmation also cancels it. A second submission cannot reuse the
original confirmation. Read the original result with “Check the transfer status.”
A different conversation cannot confirm your pending review. Exact `logout`,
`log out`, `reset` or `switch user` commands invalidate the cached teaching
session, including with trailing punctuation.

`make test` runs the native text controls without a real licence, model key or
speech key. It uses scripted model responses, the actual archived runtime and
an actual loopback MCP service. The tests also construct speech requests without
sending audio and start the real backend while replacing the Inspector process.
The versioned shared schema and illustrative mappings are in
[banking-shared](../banking-shared/README.md).

When finished, press Ctrl+C in the launcher terminal to stop both owned services,
then stop the Codespace from GitHub's Codespaces page.

The native host also fences an operation if its submission reply is lost or
malformed, even when the backend retained an accepted result. A new conversation
or logout cannot remove that fence. Reading the original status does not clear
it: this teaching build has no reconciliation command. The original reference
stays private, and fresh transfer reviews remain blocked for the process lifetime.
Confirmation is armed only after the canonical review reaches the output channel.
Failed or canceled delivery leaves no permission to submit.

Read the original status while its simulated session is still valid. Logout,
reset or the session's five-minute expiry invalidates it, so later status checks
report unavailable. The uncertainty fence stays in place.
