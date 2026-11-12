# Jack Henry banking demo

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-jack-henry-banking/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, configured by the operator as repository or organisation Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

```text
Author:        Rasa Community contributors
Assessed on:   11 November 2026, native text controls only
Assessed by:   Automated native conversation and service tests
Verified with: Scripted model, actual archived runtime and local MCP
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
```

## Run it in your browser

Codespaces gives you a computer in your browser. You do not need to install
Python or open a terminal on your own computer. Keep this page open in one
browser tab while you follow the steps in another.

Before you start, sign in to GitHub. Ask the person running the demo to check
that your account can use the three Codespaces secrets listed above. Never
paste their values into the terminal or a screenshot. Model and speech
services can incur charges. This demo uses fictional accounts only.

1. **Create the right Codespace.** Click the Codespaces button at the top of
   this page. On the creation page, keep this example's configuration
   and click **Create codespace**. If GitHub asks you to select a configuration,
   choose **Rasa resource: examples/jack-henry-banking**. Keep the recommended
   machine size. Do not choose another banking example.

2. **Wait for setup to finish.** First creation downloads the tools and can
   take several minutes; this example has no measured first-start estimate yet.
   Let setup finish before typing. The successful creation log ends with:

   ```text
   READY: examples/jack-henry-banking is installed, its secrets are set, and it passes its check. Start with the first command in its README.
   ```

   If the editor opens before that message appears, use **View → Command
   Palette**, type **Codespaces: View Creation Log**, and select it.
   **NOT READY** means setup needs attention: follow the named missing-secret
   message or ask the person running the demo. Do not continue past it.

3. **Find the terminal at the bottom.** When the browser editor opens, select
   the **TERMINAL** tab in its bottom panel. If the panel is hidden, choose
   **Terminal → New Terminal** from the editor menu. This configuration opens
   the terminal in `examples/jack-henry-banking`, the correct folder. The prompt
   ends with a cursor where you can type. You do not need to change folders.

4. **Start the demo there.** Click next to that cursor, type this single
   command, and press **Enter**:

   ```sh
   make run
   ```

   Leave this terminal open. Wait for the line beginning **Inspector (keep the
   forwarded port private):** followed by a web address. The process keeps
   running; it does not return to a new prompt until you stop it.

5. **Open Inspector.** Click the full web address printed after **Inspector**.
   If clicking does not open it, copy that address into a new browser tab.
   Keep its path and everything after the question mark. If a GitHub port
   notice appears, continue to the application. Keep the port private.
   You can find port **5005** in the editor's **PORTS** tab beside **TERMINAL**;
   its globe button opens the forwarded address. If that opens the server
   rather than Inspector, use the full address printed in the terminal.

6. **Check text, then allow the microphone.** In Inspector, start a text
   conversation and send **List my accounts.** You should see the fictional
   checking, savings and loan accounts. Choose Inspector's voice option.
   When your browser asks to use the microphone, click **Allow**. Use
   headphones if the speaker feeds sound back into your microphone. Speak
   only fictional information: the speech provider receives your audio.

7. **Try three spoken questions.** Say one sentence, then wait for the reply
   before saying the next:

   - **List my accounts.** The reply should name the fictional checking,
     savings and loan accounts.
   - **What is my checking balance?** It should say the available balance is
     **100 US dollars**.
   - **What is my next loan payment?** It should say **75 US dollars**, due
     **20 January 2026**. This is historical mock data.

   Wording may vary, but those facts must match. These questions do not move
   money. Voice worked in the operator's browser check, but replies were slow;
   response time is still being investigated. If you cannot hear a reply,
   check the browser tab's sound and microphone permissions first.

8. **Stop the demo.** Return to the editor's **TERMINAL** tab. Click inside the
   terminal running the demo, hold **Ctrl** and press **C**. A new prompt means
   the launcher has stopped its two services. Closing Inspector alone does
   not stop them.

9. **Stop the Codespace too.** Open [Your Codespaces](https://github.com/codespaces)
   in another tab. Find this Codespace, open its **…** menu and choose
   **Stop codespace**. Wait until it is stopped. To discard it, choose
   **Delete** from that menu and confirm. Closing the browser tab alone does
   not stop compute use. Stopping ends compute use; stored Codespaces can
   still use storage, so delete it when you no longer need it.

Development build: native text controls exercise all eight shared banking
actions. The operator reached Inspector and used text and voice on 12 November
2026, then ended two voice sessions because replies were slow. This is not a
qualified vendor integration.



The build uses the current catalogue pin under an explicit baseline ruling.
Rasa Pro 3.22 promotion still needs the normal release qualification; it has
not been silently adopted here.

## Setup and test details

Inspector uses private forwarded port 5005. PR CI runs `make test` with no
licence, model or speech keys. The walkthrough above is the browser start path.

The operator supplies Codespaces secrets named `RASA_PRO_LICENSE`,
`OPENAI_API_KEY` and `DEEPGRAM_API_KEY`. Values never belong in this repository,
logs or screenshots. A licence does not pay for model or speech services.
Only fictional information may be spoken. The provider receives live audio;
both speech request builders set `mip_opt_out=true`. Local tests inspect the
constructed requests without sending audio. This opt-out is not zero retention.

## Banking boundary

The `jack-henry` configuration consumes the same `banking-demo-shared` package
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
The operator's browser check reached microphone input and spoken replies;
it did not establish acceptable response time.

The following values are authored mock data, including the historical dates.
They are not current bank balances, payment dates or financial quotes.

| Ask | Expected service result |
|---|---|
| List my accounts. | `checking-A`, `savings-A` and `loan-A` only |
| What is my checking balance? | Available balance USD 100.00 |
| What is my checking ledger balance? | Ledger balance USD 110.00 |
| Show my checking history, then the next page. | One entry per page; the second page is the last |
| What is my next loan payment? | USD 75.00, due 20 January 2026 |
| Give me the supplied loan payoff for 15 January 2026. | USD 500.25 for that date |
| Give me a payoff for 16 January 2026. | Unsupported; no calculated substitute |
| Move USD 10 from my checking to my savings. | Canonical review only; no submission yet |
| Confirm transfer. | `queued`; this does not mean posted |

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
