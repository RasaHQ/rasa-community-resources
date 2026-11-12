# Fiserv Banking Hub release 11.0.0.2026.4.1 demo (voice)

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-banking-hub-11.0.0.2026.4.1/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Talk to a fictional bank by voice or by typing. This example is built on Fiserv's **current public Banking Hub release** (version 11.0.0.2026.4.1), and it is honest about what that release lets it say. The assistant lists your accounts and tells you a loan's next payment date. For a balance, a payment amount, a payoff, recent transactions or a transfer, it tells you plainly that this release cannot supply them, and why.

That is the lesson. A published API definition can describe a field without saying which values fill it. An assistant built on it must not guess.

Behind it sits a local **mock built from Fiserv's release files**. You download those files yourself; this example checks them, builds the mock from them while it starts, and the assistant talks to that mock. Nothing here contacts Fiserv, and no Fiserv key or password is needed.

**What this proves and what it does not.** The mock proves our conversation design and our code against the shapes Fiserv publishes in this release. It does **not** prove that this works with a real Fiserv system, and it makes no claim about any particular Fiserv core product. Every person, account and date is invented.

Looking for a working balance, payoff and transfer? The older [Fiserv Premier example](../fiserv-premier-11.0.0-prm/) uses Fiserv's Premier-specific definitions, which do declare those values.

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, source tests only (development build)
Assessed by:   Source and contract tests with the real release file
Verified with: Real OpenAPI validators and loopback mock built from the pinned release ZIP; live text check, spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
```

## Before you start

Get [a Rasa license](https://rasa.community/keys/#rasa), [an OpenAI key](https://rasa.community/keys/#openai), and [a Deepgram key](https://rasa.community/keys/#deepgram). Create only these three for this mock; no Fiserv trial credentials are needed. Model, speech, and Codespaces usage can incur charges.

Follow the download and upload steps before running `make run`. A setup log ending in `READY` means the environment is prepared. Wait for `Rasa server is up and running` before opening the printed Inspector link. For a typed conversation, click **Type your message**, enter the prompt, and press **Enter**. A typed check does not verify speech.

You need three things. Each takes a few minutes and costs nothing to set up.

1. **A free GitHub account.** Sign in at <https://github.com>.
2. **Three Codespaces secrets** with the Rasa licence and the two speech and language keys: `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`. Add each at <https://github.com/settings/codespaces> under **Secrets**: click **New secret**, type the name exactly, paste the value, and under **Repository access** choose this repository. Never type these into a file or a chat.
3. **Fiserv's release file** (step 1 below). It is free and public; you do not need to sign in.

## Walkthrough

Follow the steps in order. Take your time: the first start-up has a long wait.

> Each step says what to click and what you should see. If your screen does not match a step, stop and ask the maintainers before going on.

### 1. Download Fiserv's release file

1. On your own computer, open Fiserv's Banking Hub **Resources** page: <https://developer.fiserv.com/product/BankingHub/docs/resources/resources.md?branch=active>
2. Under **API Specification**, click **Download API Specifications (v11.0.0.2026.4.1)**.
3. A file named `esf-service-swagger-release-11.0.0.2026.4.1.zip` appears in your Downloads folder. **Do not open or unzip it.**

**Checkpoint:** the file is about 1.1 MB. If the link shows a different version number, stop: this example is pinned to 11.0.0.2026.4.1 and will refuse any other file.

### 2. Open the example in a Codespace

1. Click the badge at the top of this page that shows the GitHub Codespaces logo with the word “Open” on it.
2. A page titled **Create codespace** opens. Click the green **Create codespace** button.
3. Wait. A browser tab shows a code editor while it builds; this can take several minutes.

**Checkpoint:** the black panel at the bottom (the **terminal**) ends with the word `READY`.

### 3. Put the release file in the example

1. In the left panel (the **Explorer**), right-click the folder named `fiserv-banking-hub-11.0.0.2026.4.1` and choose **New Folder**. Type `vendor-inputs` and press Enter.
2. Right-click the new `vendor-inputs` folder and choose **Upload…**. Pick `esf-service-swagger-release-11.0.0.2026.4.1.zip` from your Downloads folder.

**Checkpoint:** the file now appears inside `vendor-inputs`.

### 4. Start it

1. Click once inside the terminal at the bottom of the window. It is already in the right folder.
2. Type `make run` and press Enter.
3. Wait. The first start takes a little while.

**Checkpoint:** the terminal prints `Vendor definitions: found and hash-verified` and a line starting `Open the Inspector:` followed by a long link.

If it prints `Not ready.` instead, it says what is missing in plain words: usually the release file is not in `vendor-inputs`, or one of the three secrets is not set for this repository.

### 5. Open the Inspector

1. Hold Ctrl (Command on a Mac) and click the long link in the terminal.
2. If the link does not open, click the **Ports** tab next to the terminal, find port `5005`, and click the small globe icon on its row.

**Checkpoint:** a page called **Inspector** opens in a new browser tab.

### 6. Choose typing or speaking

- **To type:** click in the message box at the bottom of the Inspector, type a sentence from the table below and press Enter. Typing does not test microphone input or spoken replies.
- **To speak:** click the microphone, then **Allow** when your browser asks. Use only fictional things. Do not say a real name, account or card number: the speech provider receives your audio.

### 7. Talk to the bank

The assistant already knows one fictional customer. Send each sentence and wait for the reply. The account names use the release's own codes: `DDA`, `SDA` and `LOAN`. The release does not say which product each code names, so the assistant never calls them checking or savings.

| Type or say | You should get |
|---|---|
| "What accounts do I have?" | `DDA-A`, `SDA-A` and `LOAN-A` |
| "When is my next loan payment on LOAN-A?" | 1 December 2026, and that the amount is not available in this release |
| "What is the balance of DDA-A?" | Not available in this release, because it does not define the code that marks an available balance |
| "What did I spend recently on DDA-A?" | Not available in this release, because its transaction definition has an error (see below) |
| "What is my payoff on LOAN-A?" | Not available in this release |
| "Move 5 dollars from DDA-A to SDA-A." | Transfers are not available in this example |
| "What is the balance of DDA-B?" | That account is not available to you |

**Checkpoint:** every answer is either a fact from the table or a plain "not available". If the assistant ever states an amount, stop and tell the maintainers: that would be a bug.

The sound is a single synthetic voice. If it takes more than a couple of seconds to answer, note how long and tell the maintainers: response time is something this project is still measuring.

### 8. Stop it

Click inside the terminal and press **Ctrl+C**.

**Checkpoint:** the terminal returns to a prompt and the Inspector tab stops working.

### 9. Delete the Codespace

A Codespace you stop but do not delete keeps using your storage. Before deleting it, preserve source changes and unique receipts or private state you need. Keep vendor inputs private.

1. Open <https://github.com/codespaces>.
2. Find this Codespace, click the three dots on its row, then **Delete**.

## Why so much is "not available"

Fiserv's release files describe the shape of each reply. For some fields they also list the allowed values; for others they leave the values to each bank. This example only uses a value when Fiserv's release or Fiserv's published documentation states it.

| What you ask for | What the release says | So this example |
|---|---|---|
| The list of your accounts | The account relationship reply, and the account codes `DDA`, `SDA`, `LOAN` (declared in the same release) | Lists them by their codes |
| A loan's next payment date | A plain date field, `NextPmt.PmtDt` | Gives the date |
| A loan's next payment amount | The amount sits in a list of parts labelled by `CompositeCurAmtType`, which has no declared values | Says the amount is not available |
| An available balance | Balances are labelled by `BalType`, which has no declared values here | Says it is not available |
| A payoff | Not a labelled balance in this release; a separate payoff service exists, but its definition has its own errors and is not part of this example | Says it is not available |
| Recent transactions | **The definition has an error.** In `AcctTrnService` 11.0.0, `BaseKeysType` is declared as a string, and the account and transaction key types are built as "a string *and* an object". Nothing can be both, so no request naming an account and no reply with any transaction can pass Fiserv's own definition | Says it is not available |
| A transfer | The transfer type field has no declared values | Offers no transfer at all |

Success itself follows Fiserv's published response codes: a reply counts only with HTTP 200 and EFX status `0` with severity `Info`. Status `1120` (Info) means nothing matched. Warnings and errors are never treated as success. Every reply in this release requires only a status, so a reply that passes the definition is not, by itself, a success.

Fiserv may publish a corrected release. This example then needs a reviewed update; it will not accept a changed file on its own.

## What is inside

| File or folder | What it does |
|---|---|
| `bh_demo/contract.py` | Checks the downloaded ZIP and builds request and response checks from three of Fiserv's release files |
| `bh_demo/mock.py` | The local mock bank: the release's paths and bodies, fictional data, every reply checked against the release |
| `bh_demo/client.py` | Our direct client for two release operations, with Fiserv's success rules |
| `bh_demo/server.py` | The MCP server the assistant calls: exactly seven tools |
| `bh_demo/host.py` | Identity simulator, permitted reads, and the plain "not available" answers |
| `skills/banking/` | The assistant's skill and its tool bindings |

The two operations used are the party account relationship inquiry (`/partyacctrel/secured`) and the account inquiry (`/accounts/secured`). The transaction definition (`/acctTrn/secured`) is loaded too, so the tests can prove the error described above.

The assistant also has one Rasa-side trigger, `banking_submit_transfer`. It is not an MCP tool, carries no authority, and in this example can never send anything.

### What stays out of this repository

No Fiserv file is stored here: no ZIP, no extracted definition and no copy of its schemas. `vendor-inputs/` is ignored by Git. If the file you supply is not exactly the one this example was written for, it refuses to start rather than guess.

### Honest limits

- **Wire shape, not behaviour.** The mock validates every request and its own replies against the release. That does not tell you how a real Fiserv system answers.
- **No product claim.** These are Fiserv's generic Banking Hub definitions. They do not say which values a particular Fiserv core uses.
- **One mock value is invented.** The release requires an account status code but declares no values for it. The mock sends `FictionalMockStatus`; the client never reads it.
- **Identity is simulated.** One fixed fictional caller. This is not bank sign-in.
- **Not done yet:** a live text check with a real model, a recorded spoken run, and response-time measurement.

## For developers

```bash
make test           # source, host and server tests; contract tests skip without the release file
make contract-test  # the contract tests (need the release file; skipped without it)
make validate       # Rasa project validation
```

CI has no Fiserv file, so contract-dependent tests print that they were skipped. A skipped input never qualifies the contract.

A live text check goes through the REST channel with a real model (a few cents, needs the three secrets and the release file). It is not part of `make test`:

```bash
uv run --locked python tests/live_text_check.py
```
