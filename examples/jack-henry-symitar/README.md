# Talk to a fictional credit union: a Rasa voice demo with a Jack Henry Symitar mock

## What this example shows

Ask for your balance, explore recent transactions, check a loan payment, and request a transfer between your checking and savings accounts—all through a conversation. The assistant talks to a **local simulation of the Jack Henry Symitar core through the Symitar-in-Platform v1 web API**. It was tested with **Jack Henry Symitar files as published 12 Nov 2026, 22:38 UTC**; see [Vendor files and versions](#vendor-files-and-versions).

> **Demo status:** typed native checks and isolated software development kit (SDK) snapshot loading have been recorded. A cold trained-archive check and a complete spoken transfer walkthrough remain outstanding. The voice steps below describe the intended experience, not a verified microphone-to-spoken-reply result. Setup and response time have not been measured for this walkthrough.
>
> All people, accounts, and amounts are fictional. No banking request goes to a real credit union. Model and speech services are external, so use only fictional information.

You will run it in your browser using GitHub Codespaces. You do not need to install Python on your computer or have a Jack Henry account.

**Your first goal:** open the assistant and ask, “What is available in checking?” With the initial demo data, the expected answer is **USD 1,200.50 available**.

### What you will learn

- Connect a conversational assistant to banking tools.
- Check requests and responses against published API definitions.
- Require the next actual user turn to confirm a reviewed transfer.
- Keep an uncertain transfer outcome unresolved rather than resending it.

You can follow the walkthrough without knowing banking APIs or the tools used here. These terms are explained in [What is happening](#what-is-happening), after your first conversation.

### Qualification record

<details>
<summary>Qualification recorded before this walkthrough rewrite</summary>

```text
Author:        Rasa Community contributors
Assessed on:   2026-11-12
Assessed by:   Contract, state and transport checks; native voice qualification recorded separately
Verified with: rasa-pro 3.21.0.dev5, Python 3.12
Record status: Development branch; see the PR for current native qualification
Industry:      Banking
You learn:     How to connect a voice assistant to banking tools and never resend a transfer whose outcome is unclear.
Catalog name:  Jack Henry Symitar credit union voice demo
```

</details>

### The other Jack Henry example

For the other Jack Henry API, see the separate [SilverLake jXchange example](../jack-henry-silverlake/). SilverLake uses simple object access protocol (SOAP) messages in extensible markup language (XML). Symitar uses a representational state transfer (REST) API.

## What you need

| You need | Why |
|---|---|
| A [GitHub account](https://github.com) with Codespaces access | Runs the example in a cloud development environment |
| A Rasa Developer Edition license | Enables the Rasa runtime |
| An OpenAI API key with available API usage | Provides the language model |
| A Deepgram API key with available API usage | Provides speech recognition and spoken replies |
| Four Symitar-in-Platform v1 definition files | Supplies the contract used by the mock |
| A browser; a microphone if you want to try speech | Opens the Inspector; typing is also available |

**Cost:** the Rasa Developer Edition license is free within its license limits. Model, speech, and Codespaces usage can incur charges. Check your accounts before starting. The local banking mock needs no bank credentials.

**Time:** first-build and walkthrough duration have not been measured. Allow time for environment creation and model training.

<a id="walkthrough"></a>

### 1. Get your license and API keys

[rasa.community/keys](https://rasa.community/keys/) explains how to get each one. A license enables a product. An API key lets this application use a service through your account. Treat both like passwords.

| Secret name—copy exactly | Where to get its value |
|---|---|
| `RASA_LICENSE` | [Get a free Rasa Developer Edition license](https://rasa.community/keys/#rasa) |
| `OPENAI_API_KEY` | [Create an OpenAI API key and check billing](https://rasa.community/keys/#openai) |
| `DEEPGRAM_API_KEY` | [Create a Deepgram project API key](https://rasa.community/keys/#deepgram) |

**Checkpoint:** you have all three values. Keep them out of source files, chats, issues, and screenshots.

### 2. Add the keys to GitHub Codespaces

1. Open your [personal Codespaces settings](https://github.com/settings/codespaces).
2. Under **Secrets**, choose **New secret**.
3. Enter `RASA_LICENSE` as the name.
4. Paste only the value, without `RASA_LICENSE=` or surrounding quotes.
5. Under **Repository access**, select `RasaHQ/rasa-community-resources`.
6. Choose **Add secret**.
7. Repeat for `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`.

These are Codespaces secrets, not GitHub Actions secrets. If you use your own fork, select that repository instead.

**Checkpoint:** all three names appear in your Codespaces secret list, with access to the repository you will use. Their saved values are hidden; that is expected.

If the Codespace already exists, stop and restart it after adding or changing a secret. See [GitHub's instructions](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces).

## Start it

This example runs only in GitHub Codespaces, which gives everyone the same tested setup. There are no local setup steps: running it on your own computer is not tested or supported. Follow these steps in order. Each step includes a checkpoint.

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-jack-henry-symitar/devcontainer.json)

- **Before starting:** save `RASA_LICENSE`, `OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` as personal Codespaces secrets. [Get the keys](https://rasa.community/keys/) and follow [the walkthrough](#walkthrough).
- **Use this badge:** it selects this example's development environment.
- **After the setup log says `READY`:** upload the four definitions into `vendor-inputs/`, then run `make run`.
- **Open the assistant:** wait for `Rasa server is up and running`, then follow the printed Inspector link. The server uses port `5005`.
<!-- codespaces:end -->

### 3. Open the example

1. Click the Codespaces badge above.
2. On the creation page, choose **Create codespace**.
3. Wait for the browser editor and environment setup to finish.
4. Look for `READY` in the setup log.

The terminal is the panel where you enter commands. It opens in this example's folder. If needed, choose **Terminal → New Terminal**.

**Checkpoint:** the terminal's current folder ends in `examples/jack-henry-symitar`. Setup is ready; the assistant is not running yet.

### 4. Download and upload the four API definitions

Open each official file in your browser and save its original YAML bytes. YAML is a text format for these API definitions. Save the file itself, not the rendered webpage.

| Definition | Official file | Destination inside this example |
|---|---|---|
| Accounts | [accounts.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/accounts/accounts.yaml) | `vendor-inputs/accounts/accounts.yaml` |
| Transactions | [transactions.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transactions/transactions.yaml) | `vendor-inputs/transactions/transactions.yaml` |
| Loans | [loans.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/loans/loans.yaml) | `vendor-inputs/loans/loans.yaml` |
| Transfers | [transfers.yaml](https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transfers/transfers.yaml) | `vendor-inputs/transfers/transfers.yaml` |

In the terminal, create the destination folders:

```bash
mkdir -p vendor-inputs/accounts vendor-inputs/transactions vendor-inputs/loans vendor-inputs/transfers
```

The Explorer is the file-and-folder panel in the editor. Right-click each destination folder, choose **Upload…**, and select its matching saved file.

**Checkpoint:** all four files are in the locations shown above. The program checks their hashes before building the mock. A hash is a fingerprint of a file's exact bytes. A missing file stops startup. A newer file starts the example only if it still accepts everything the example sends and reads and its replies are unchanged (see [Vendor files and versions](#vendor-files-and-versions)); do not edit the expected hashes to get past a stop.

This example has no `make download` target. Download and upload the four files yourself. Vendor definitions are ignored by Git and are not included in this repository.

### 5. Start the assistant

In this example's terminal, run:

```bash
make run
```

The launcher checks the supplied files and secrets, starts the local mock and banking tools, trains the project, and starts the Inspector server on port `5005` by default.

Open the Inspector URL printed by the terminal. Leave this terminal running. If the link does not open, use the editor's **Ports** tab and the browser button for the Inspector port. Keep the other local ports private.

**Checkpoint:** wait for `Rasa server is up and running` before sending a message. A printed link alone is not proof that startup or training has completed. Read any reported error before continuing.

### 6. Open the Inspector and choose text or speech

For a text conversation, click **Type your message**, type a prompt, and press **Enter**. This lets you try the conversation without a microphone.

For speech, allow microphone access when the browser asks and use the Inspector microphone. The speech provider receives your audio. A typed check does not establish that speech recognition or spoken replies work.

**Checkpoint:** the Inspector is connected and accepts your first message. The complete spoken path remains unverified.

### Stop and clean up

1. Press **Ctrl+C** in the terminal running `make run`.
2. Wait for its Inspector, Model Context Protocol (MCP), and mock processes to stop.
3. Open [your Codespaces](https://github.com/codespaces) and stop the Codespace when finished.
4. Before deleting it, preserve any private fixture state or work you need. Never commit secrets, vendor definitions, or private journals.

Closing the browser or stopping the application does not stop Codespaces compute usage. Stopping a Codespace ends compute use; retained storage still counts toward storage usage. Deleting it removes its local files.

## Try these conversations

Type or say these lines in the Inspector, in this order:

```text
What is available in checking?
What accounts can I use?
What did I spend in checking from November 1 to November 12, 2026?
What is my car loan payment?
What is the payoff quote for my car loan on November 13, 2026?
Verify me.
Review a transfer of 1.25 from checking to savings.
Yes.
```

The initial available balance in checking is **USD 1,200.50**. Wording can vary; check the facts rather than expecting one exact sentence.

### The full checked sequence

#### Ask your first questions

| Say | Expected information | What you are testing |
|---|---|---|
| “What accounts can I use?” | Deposit aliases `checking` and `savings`; loan alias `car` | Finding the fictional customer's accounts |
| “What did I spend in checking from November 1 to November 12, 2026?” | The returned transactions for that range (fixture: November 10 and 11, 2026), without claiming complete history | Reporting only the available data; the history lookup needs an explicit date range |
| “What is my car loan payment?” | Current payment due **USD 250.75**, next due **December 1, 2026** | Keeping current due, regular payment, and past due separate |
| “What is the payoff quote for my car loan on November 13, 2026?” | A dated quote from the fictional loan fixture | Using the requested date rather than guessing a payment |

The dates are fixed fixture data, not automatically updated to today's date. A loan payment is an installment; a payoff quote is an amount for settling the loan on a date.

#### Try a transfer with explicit confirmation

| Step | Say | Expected behavior |
|---|---|---|
| 1 | “Verify me.” | The host replies “Your simulated verification was refreshed. This is not bank sign-in.” only after it refreshes simulated verification from this turn |
| 2 | “Review a transfer of 1.25 from checking to savings.” | The host reads the exact amount and accounts, then asks for confirmation |
| 3 | “Yes.” | The host reports acceptance and explains that accepted does not mean posted; this must be the immediately next actual user turn |

Verification is simulated. This is not bank sign-in. A review that was changed, canceled, expired, or not delivered cannot authorize submission. An unrelated next message cancels the review; request a new review before confirming again.

A successful fixture transfer may have no receipt. A missing receipt does not establish failure, and an acceptance is not proof of posting. If a response is lost after dispatch, the outcome is unknown. Do not retry or delete state to clear the hold. The hold applies across conversations for that fictional customer; reads and local status remain available.

## What is happening

The assistant handles the conversation. The host controls transfer authority. The bank is a local mock using fictional data.

```text
You (Inspector: text or speech)
  -> Rasa and the language model    understand you and write replies
  -> MCP server in this folder      seven read, review, and status tools
  -> Host policy and journal        private host: review, confirmation, one send
  -> Symitar client and mock        fictional bank, checked against the four definitions
```

| Component | Role |
|---|---|
| Inspector and speech services | Present text or speech conversations |
| Rasa and the language model | Interpret requests and compose replies |
| This folder's MCP server | Exposes seven read, review, and status tools |
| Host policy and journal | Own identity simulation, review, confirmation, one send, and unresolved state |
| Symitar client and contract mock | Build and check requests against the four supplied definitions |

MCP means Model Context Protocol, the interface used for tools. REST uses hypertext transfer protocol (HTTP) requests for the banking API. OpenAPI describes the permitted request and response structures. All banking traffic stays on loopback, inside this development environment. Model and speech services remain external.

The model has no submit, confirm, reset, or identity-creation tool. The trusted host observes the next actual user turn before deciding whether it may send.

### What has been verified—and what has not

The transfer reply controls have source tests. A fresh end-to-end run of this revised walkthrough is still outstanding.

| Item | Recorded status |
|---|---|
| Author | Rasa Community contributors |
| Assessment date | November 12, 2026 |
| Environment | `rasa-pro 3.21.0.dev5`, Python 3.12; development build |
| Source, mock, and snapshot controls | Tested; real SDK snapshot loads all eight bindings (the seven tools plus the Rasa-side verify trigger) without the live source directory |
| Typed native conversation | Recorded fixture checks; separate from cold trained-archive qualification |
| Cold trained archive | Qualification still outstanding |
| Complete spoken transfer | Not proved |
| Setup duration and response time | Not measured for this walkthrough |
| Real Symitar integration | Not established by this mock or its checks |

### Limits before adapting the demo

- Schema-valid data does not prove compatibility with a real credit union installation.
- Identity and verification are simulated for one fictional customer.
- Missing data stays unavailable; do not substitute a regular payment for the amount currently due.
- No receipt does not mean failure; acceptance does not mean posting.
- A lost response stays unknown and blocks resending across conversations and restarts.
- The fixture is not evidence of bank authentication, production idempotency, or zero provider retention.

## Vendor files and versions

This example was tested with **Jack Henry Symitar files as published 12 Nov 2026, 22:38 UTC**. Jack Henry serves each file from one address that always returns its newest version, so you may download newer files. [VENDOR-FILES.md](VENDOR-FILES.md) lists the exact files and what the example checks when yours are newer. [CHANGELOG.md](CHANGELOG.md) records what changed in each version and in the example.

If the start-up says Jack Henry changed something this example uses, it names the operation and field. Your files are newer than this example; please open an issue.


## Change it

Change one fictional value and see it in a reply. The mock reads its fictional bank data from `fixtures/fictional.json`.

1. Stop every copy of the example (press **Ctrl+C** in the terminal running `make run`).
2. Open `fixtures/fictional.json`. In the `checking` entry under `shares`, change `"available": "1200.50"` to another fictional amount, such as `"available": "1300.50"`.
3. The saved fixture state records a fingerprint of this file, so the mock refuses a changed file until you start a new fictional exercise. Run the reset command from [Start a new fictional exercise](#start-a-new-fictional-exercise) below.
4. Run `make run` again and ask, “What is available in checking?” The reply should use your new amount.

To undo the change, restore `"1200.50"` and start another new fictional exercise.

### Start a new fictional exercise

With every copy of the example stopped, run:

```bash
make reset-fixture REASON="new fictional exercise"
```

This audited reset preserves old databases and their hashes, acknowledges that unresolved transfers remain unresolved, and starts a new fictional exercise. It never resolves or retries an earlier transfer. Do not delete the state files in `.runtime/` to clear a hold.

## Troubleshooting

### A required secret is missing

Check its name and repository access, then stop and restart the Codespace. See [What you need](#what-you-need).

### A vendor file is missing or has a different hash

Check its exact destination and original bytes; do not weaken the hash check. See [Vendor files and versions](#vendor-files-and-versions).

### The Inspector is unavailable

Wait for server readiness, check terminal errors, and use port `5005` in the Ports tab.

### Other problems

| What you see | What to check or do |
|---|---|
| Setup has not printed `READY` | Read the setup error before running the assistant |
| `make download` fails | This example has no download target; use the four manual download links in [Start it](#start-it) |
| A read or transfer says verification expired | Say “Verify me,” then make a new request |
| A transfer review was canceled | Request a new review; repeating an old confirmation does not restore it |
| A transfer outcome is unknown | Keep the journal and do not resend; see [Start a new fictional exercise](#start-a-new-fictional-exercise) |
| The spoken path does not work | Record the visible error without keys or private data; voice qualification remains outstanding |

## Files

### Explore the code

| File or folder | What to look for |
|---|---|
| `skills/banking/`, `lib/native_adapter.py` | Banking instructions, native bindings, and raw-turn observation |
| `server.py` | This example's seven MCP tools |
| `host.py`, `journal.py` | Private authority, review, confirmation, and retained transfer state |
| `vendor_client.py`, `mock_server.py` | Symitar-shaped client and fictional mock |
| `contract_inputs.py`, `recorded_exchanges.py` | Four exact file hashes, OpenAPI checks, and the recorded traffic checked against newer files |
| `vendor_models/`, `vendor_api.py`, `make_models.py` | Pydantic models generated from the four pinned Jack Henry files (names, types, required fields, allowed values; no vendor descriptions), and the map from each operation to its request and reply model. The host builds requests and reads replies through them |
| `fixtures/fictional.json` | Fictional accounts, balances, transactions, and loan data |

### Supported banking operations

Six vendor operations support the seven tools. These counts describe different interfaces.

| Vendor operation | Purpose |
|---|---|
| `findAccountBy` | Find the permitted account |
| `findAccountByWithBalances` | Read account balances |
| `searchAccountTransactions` | Read the returned transaction history |
| `searchLoans` | Read loan information |
| `calculateLoanPayoffQuote` | Request a quote for a supplied date |
| `postTransfer` | Submit the host-authorized transfer |

### Run the checks

Run these commands in another terminal from the example folder:

```bash
make test
make contract-test
make validate
```

To regenerate the models after a vendor update (needs the four files in `vendor-inputs/`), run `make models`; `make models-check` fails if the committed models differ from a fresh generation. The generator, datamodel-code-generator, is installed only for these two commands.

`make test` runs source, state, transport, and snapshot controls. `make contract-test` runs the vendor contract tests. Contract-dependent tests skip without the four vendor files; a skip does not prove conformance. `make validate` checks the Rasa configuration. None of these is a spoken conversation check.
