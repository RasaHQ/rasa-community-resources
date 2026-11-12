# Run the fictional Symitar voice example

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-jack-henry-symitar/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

```text
Author:        Rasa Community contributors
Assessed on:   2026-11-12
Assessed by:   Contract, state and transport checks; native voice qualification recorded separately
Verified with: rasa-pro 3.21.0.dev5, Python 3.12
Status:        Development branch; see the PR for current native qualification
```

Talk to a local fictional banking assistant. It uses this folder's own MCP server,
OpenAPI contract mock, fictional data, tests and voice configuration. It never
connects to a bank. The customer, balances, transactions and loan are invented.

The model can request seven read, review and status tools. It cannot create an
identity, confirm a review, submit a transfer, reset the fixture or clear an
unknown outcome. The trusted host handles the next actual confirmation.

## 1. Save your existing personal Codespaces secrets

In GitHub, open **Settings → Codespaces → New secret**. Add each secret below and
allow it access to `RasaHQ/rasa-community-resources`:

- `RASA_LICENSE`: your Rasa Pro Developer Edition license.
- `OPENAI_API_KEY`: the model provider key for this exercise.
- `DEEPGRAM_API_KEY`: speech recognition and spoken replies.

The mock and contract tests need none of these secrets. The voice agent uses
provider services and may incur charges. Never paste a secret into chat, a tool
argument, a source file or a screenshot. After changing secret access, stop and
reopen the Codespace so it receives the new values.

## 2. Open the example and find the terminal

Use this example's Codespaces button once the PR is merged. Its setup selects
this folder and the locked environment. Wait for `READY`; a missing-secret notice
is a setup condition, not a running voice agent.

Open **Terminal → New Terminal** in the browser editor. The terminal is the panel
at the bottom. Its folder should end in `examples/jack-henry-symitar`. If it does
not, enter:

```bash
cd /workspaces/rasa-community-resources/examples/jack-henry-symitar
```

## 3. Supply the four vendor definitions manually

Open each official definition below in your browser and save its original YAML
file. Do not copy rendered page text or change the file contents.

| Definition | Official file | Destination in this folder |
|---|---|---|
| Accounts | [accounts.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/accounts/accounts.yaml) | `vendor-inputs/accounts/accounts.yaml` |
| Transactions | [transactions.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transactions/transactions.yaml) | `vendor-inputs/transactions/transactions.yaml` |
| Loans | [loans.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/loans/loans.yaml) | `vendor-inputs/loans/loans.yaml` |
| Transfers | [transfers.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transfers/transfers.yaml) | `vendor-inputs/transfers/transfers.yaml` |

Create the destination folders, then upload each saved file into the matching
folder in the editor's file explorer:

```bash
mkdir -p vendor-inputs/accounts vendor-inputs/transactions vendor-inputs/loans vendor-inputs/transfers
```

These files are ignored by Git. This example does not download them, execute
anything in them, or publish their contents. `contract_inputs.py` checks all four
SHA256 pins before the mock is built. A missing file stops launch; a changed hash
fails rather than silently accepting a different vendor release.

## 4. Start and open the voice conversation

In this folder, run:

```bash
make run
```

The launcher checks the local inputs and required secrets, owns the local MCP
and mock processes, trains the native project, then starts the Inspector. Read
the printed Inspector URL and open it. If the browser does not open it directly,
open the **Ports** tab beside Terminal and choose the Inspector port's browser
button. Keep the MCP and mock ports private.

Allow microphone access when your browser asks. Use the microphone in the
Inspector to speak. Typing is also available, but a typed check is not a speech
qualification.

## 5. Try the fictional questions

Start with: “What accounts can I use?” The permitted deposit aliases are
`checking` and `savings`; the loan alias is `car`.

- “What is available in checking?” The baseline available balance is USD 1,200.50.
- “What is my car loan payment?” Current payment due is USD 250.75. The next due
  date is December 1, 2026. Regular payment, minimum payment and past due are
  different fixture values; none is a substitute for current payment due.
- “What is the payoff quote for November 13, 2026?” The dated fictional quote
  uses that date. It does not make a payment or change a balance.
- “Review a transfer of 1.25 from checking to savings.” Read or listen to the
  host's exact review, then say “yes” as the immediately next user turn. A changed
  amount, changed destination, cancellation, expired assurance or missing review
  delivery prevents submission.

A successful fixture transfer may have no receipt. That does not make it a
failure. If a response is lost after dispatch, the outcome is unknown: do not
retry. The hold covers new transfer details and new conversations for this
fictional principal. Reads and local status remain available.

## 6. Stop the exercise

Press **Ctrl+C** in the terminal running `make run`. Wait for the owned Inspector,
MCP and mock processes to stop. Stop the Codespace from GitHub's Codespaces page
when finished; closing the browser tab does not stop its billed runtime.

Reopening the same fixture preserves its state and unresolved transfer holds.
A conversation restart is not a fixture reset. A deliberate reset must be run
locally with the services stopped, acknowledgement and a reason; it preserves
old state and writes an audit before a new fictional epoch. It never resolves
or retries an earlier transfer. With every copy stopped, run:

```bash
make reset-fixture REASON="new fictional exercise"
```

Old databases remain in `.runtime/` with their hashes in the reset audit. Do not
delete state files to clear a hold.

## Checks and limits

Run `make test` for local controls. Without the four definitions, contract tests
explicitly skip and launch refuses; skipped tests do not establish conformance.
With the pinned inputs, checks validate raw wire types, nullable responses,
fictional state, authority and private confirmation boundaries. Native voice and
first-start receipts are separate from unit and HTTP test results.

This fixture is not customer authentication, vendor idempotency, production
banking or proof of zero provider retention. Only fictional data belongs in the
exercise. No live adapter, real payment or vendor credential is included.
