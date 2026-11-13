# Fiserv Banking Hub release 11.0.0.2026.4.1 demo (voice)

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-banking-hub-11.0.0.2026.4.1/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **Before the first command:** Download Fiserv's release ZIP and upload it to `vendor-inputs/` in this folder (README steps 1 and 3); without it `make run` stops with a plain message.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** `Vendor definitions: found and hash-verified`, then `Rasa server is up and running`; only then open the printed Inspector link.
<!-- codespaces:end -->

## What this example shows

Talk to a fictional bank by voice or by typing. The example is built and tested on Fiserv's **Banking Hub release 11.0.0.2026.4.1**, Fiserv's current public Banking Hub release. The release file and its version facts are in [Vendor files and versions](#vendor-files-and-versions).

### About this example

This example is honest about what that release lets it say. The assistant lists your accounts, reads the available balance of a `DDA` account, tells you a loan's next payment amount and date, and reviews and sends an own-account transfer only after you confirm it. For recent transactions or a payoff, it tells you plainly that this release cannot supply them, and why.

That is the lesson. A published API definition can describe a field without saying which values fill it. An assistant built on it must not guess: it uses a value only where Fiserv publishes one, says where that value comes from, and says "not available" everywhere else.

Behind it sits a local **mock built from Fiserv's release files**. You download those files yourself; this example checks them, builds the mock from them while it starts, and the assistant talks to that mock. Nothing here contacts Fiserv, and no Fiserv key or password is needed.

**What this proves and what it does not.** The mock proves our conversation design and our code against the shapes Fiserv publishes in this release. It does **not** prove that this works with a real Fiserv system, and it makes no claim about any particular Fiserv core product. Every person, account and date is invented.

Looking for recent transactions and a payoff? The [Fiserv Premier example](../fiserv-premier-11.0.0-prm/) uses Fiserv's Premier-specific definitions, which supply both.

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, source tests only (development build)
Assessed by:   Source and contract tests with the real release file
Verified with: Real OpenAPI validators and loopback mock built from the pinned release ZIP; spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
Industry:      Banking
You learn:     How a voice assistant uses only the values a published banking API defines, and never guesses the rest.
Catalog name:  Fiserv Banking Hub voice banking demo
```

## What you need

Get [a Rasa license](https://rasa.community/keys/#rasa), [an OpenAI key](https://rasa.community/keys/#openai), and [a Deepgram key](https://rasa.community/keys/#deepgram). The page <https://rasa.community/keys/> explains how to get each one. Create only these three for this mock; no Fiserv trial credentials are needed. Model, speech, and Codespaces usage can incur charges.

You need three things. Each takes a few minutes and costs nothing to set up.

1. **A free GitHub account.** Sign in at <https://github.com>.
2. **Three Codespaces secrets** with the Rasa licence and the two speech and language keys: `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`. Add each at <https://github.com/settings/codespaces> under **Secrets**: click **New secret**, type the name exactly, paste the value, and under **Repository access** choose this repository. Never type these into a file or a chat.
3. **Fiserv's release file** (step 1 in [Start it](#start-it)). It is free and public; you do not need to sign in.

## Start it

This example runs only in GitHub Codespaces, which gives everyone the same tested setup. There are no local setup steps: running it on your own computer is not tested or supported.

Follow the download and upload steps before running `make run`. A setup log ending in `READY` means the environment is prepared. Wait for `Rasa server is up and running` before opening the printed Inspector link. For a typed conversation, click **Type your message**, enter the prompt, and press **Enter**. A typed check does not verify speech.

Follow the steps in order. Take your time: the first start-up has a long wait.

> Each step says what to click and what you should see. If your screen does not match a step, stop and ask the maintainers before going on.

### 1. Download Fiserv's release file

1. On your own computer, open Fiserv's Banking Hub **Resources** page: <https://developer.fiserv.com/product/BankingHub/docs/resources/resources.md?branch=main>
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

```bash
make run
```

**Checkpoint:** the terminal prints `Vendor definitions: found and hash-verified` and a line starting `Open the Inspector:` followed by a long link. The link is not usable yet: keep waiting until the terminal also prints `Rasa server is up and running`.

If it prints `Not ready.` instead, it says what is missing in plain words: usually the release file is not in `vendor-inputs`, or one of the three secrets is not set for this repository. See [Troubleshooting](#troubleshooting).

### 5. Open the Inspector

1. Hold Ctrl (Command on a Mac) and click the long link in the terminal.
2. If the link does not open, click the **Ports** tab next to the terminal, find port `5005`, and click the small globe icon on its row.

**Checkpoint:** a page called **Inspector** opens in a new browser tab.

### 6. Choose typing or speaking

- **To type:** click in the message box at the bottom of the Inspector, type a sentence from the table in [Try these conversations](#try-these-conversations) and press Enter. Typing does not test microphone input or spoken replies.
- **To speak:** click the microphone, then **Allow** when your browser asks. Use only fictional things. Do not say a real name, account or card number: the speech provider receives your audio.

### 7. Talk to the bank

Go to [Try these conversations](#try-these-conversations) and send each sentence there.

### 8. Stop it

Click inside the terminal and press **Ctrl+C**.

**Checkpoint:** the terminal returns to a prompt and the Inspector tab stops working.

### 9. Delete the Codespace

A Codespace you stop but do not delete keeps using your storage. Before deleting it, preserve source changes and unique receipts or private state you need. Keep vendor inputs private.

1. Open <https://github.com/codespaces>.
2. Find this Codespace, click the three dots on its row, then **Delete**.

## Try these conversations

Start with these lines, one at a time:

- "What accounts do I have?"
- "What is the balance of DDA-A?"
- "When is my next loan payment on LOAN-A?"
- "What did I spend recently on DDA-A?"
- "Verify me."
- "Move 25 dollars from DDA-A to SDA-A."
- "Confirm transfer."

Each start uses different fictional balances and loan payments (this release has no transaction history to vary). The first line `make run` prints shows the seed, for example `Demo data seed: 4821; set DEMO_SEED=4821 to get the same data again.` Start with `DEMO_SEED=4821 make run` to get that run's data again. To follow the checked sequence below exactly, start with `DEMO_SEED=0 make run`: seed 0 is the reference data the tables use.

### The full checked sequence

The assistant already knows one fictional customer. Send each sentence and wait for the reply. The account names use the release's own codes: `DDA`, `SDA` and `LOAN`. The release does not say which product each code names, so the assistant never calls them checking or savings.

| Type or say | You should get |
|---|---|
| "What accounts do I have?" | `DDA-A`, `SDA-A` and `LOAN-A` |
| "What is the balance of DDA-A?" | **USD 1,250.00** available |
| "What is the balance of SDA-A?" | Not available: the only available-balance example Fiserv publishes is for a `DDA` account |
| "When is my next loan payment on LOAN-A?" | **USD 182.40**, due **1 December 2026** |
| "What did I spend recently on DDA-A?" | Not available in this release, because its transaction definition has an error (see below) |
| "What is my payoff on LOAN-A?" | Not available in this release |
| "What is the balance of DDA-B?" | That account is not available to you |

**Checkpoint:** every amount matches the table, and everything else is a plain "not available". If the assistant ever states an amount that is not in the table, stop and tell the maintainers: that would be a bug.

Now try a transfer. Send these one at a time, in this order:

| Type or say | You should get |
|---|---|
| "Verify me." | "Your simulated verification was refreshed. It lasts about a minute." |
| "Move 25 dollars from DDA-A to SDA-A." | "Review: transfer USD 25.00 from DDA-A to SDA-A. To submit exactly this transfer, say confirm transfer next. Anything else cancels this review." |
| "Confirm transfer." | "The transfer request was accepted. Accepted does not mean posted." |
| "Move 7 dollars from DDA-A to SDA-A." | A new review for USD 7.00, in the same words |
| "No, do not transfer." | The review was cancelled and nothing was sent |
| "Confirm transfer." | There is no active review: ask for a new transfer |

**Checkpoint:** you heard each review once, and "accepted" only after you said "confirm transfer". Accepted means the bank took the request, not that the money has posted. After the first transfer, "What is the balance of DDA-A?" says **USD 1,225.00**. Verification lasts about a minute: if a transfer says it needs verification, say "Verify me." and ask again.

The sound is a single synthetic voice. If it takes more than a couple of seconds to answer, note how long and tell the maintainers: response time is something this project is still measuring.

## What is happening

```text
You (voice or typing, in the Inspector)
  -> Rasa assistant (model + the banking skill in skills/banking/)
  -> MCP server (bh_demo/server.py, exactly seven tools)
  -> private host (bh_demo/host.py: identity simulator, permitted reads,
     transfer review, one confirmed send, private journal)
  -> local mock bank (bh_demo/mock.py), built from Fiserv's release file
     and checked against it by bh_demo/contract.py
```

Nothing in this chain contacts Fiserv.

The operations used are the party account relationship inquiry (`/partyacctrel/secured`), the account inquiry (`/accounts/secured`) and Add Transfer (`/transfers`). The transaction definition (`/acctTrn/secured`) is loaded too, so the tests can prove the error described below.

The assistant also has two Rasa-side triggers, `banking_refresh_verification` and `banking_submit_transfer`. They are not MCP tools and carry no authority: the host refreshes verification only from your own words "verify me", and sends a transfer only after your very next words are exactly "confirm transfer".

### What the release supplies, and where each value comes from

Fiserv's release files describe the shape of each reply. For some fields they also list the allowed values; for others they leave the values to each bank. This example uses a value only when Fiserv publishes it. Where the release lists none but Fiserv's official sample collection shows one, the example says so and uses exactly that value.

| What you ask for | What Fiserv publishes | So this example |
|---|---|---|
| The list of your accounts | The account relationship reply, and the account codes `DDA`, `SDA`, `LOAN` (declared in the same release) | Lists them by their codes |
| An available balance | The release labels balances by `BalType` and declares no values. Fiserv's official Premier sample collection (R2026.3.3, *Account Service / 1.3. Update Account - DDA*) labels the available balance `Avail`, in a request that updates a `DDA` account | Reads the one `DDA` balance labelled exactly `Avail`. No other entry, no first entry and no ledger balance is ever used instead. For an `SDA` account it says not available |
| A loan's next payment | The date is a plain field, `NextPmt.PmtDt`. The amount sits in a list of parts labelled by `CompositeCurAmtType`, which declares no values. The same sample collection's *Account Service / 4.2. Get Account - LOAN* replies label the payment `Total` | Gives the date, and the amount of the one part labelled exactly `Total`, never another part or a sum. A missing or repeated `Total` is not available |
| A payoff | Not a labelled balance in this release; a separate payoff service exists, but its definition has its own errors and is not part of this example | Says it is not available |
| Recent transactions | **The definition has an error.** In `AcctTrnService` 11.0.0, `BaseKeysType` is declared as a string, and the account and transaction key types are built as "a string *and* an object". Nothing can be both, so no request naming an account and no reply with any transaction can pass Fiserv's own definition | Says it is not available |
| A transfer | Add Transfer (`XferAddOper`, `POST /transfers`) declares HTTP **201** for success, and the transfer status as `Valid`, `Rejected` or `Deleted`. Its `XferInfo.TransferType` field is optional and declares no values; Fiserv's official Add Transfer samples leave it out | Leaves `TransferType` out, as the samples do, and sends one immediate transfer from a `DDA` account to another `DDA` or an `SDA` account of the same customer, with no recurrence. It says accepted only for HTTP 201 with status `0` and `Valid` |

Success itself follows Fiserv's published response codes: a read counts only with HTTP 200 and EFX status `0` with severity `Info`, and a transfer only with HTTP 201, status `0`, `Info` and `Valid`. Status `1120` (Info) means nothing matched. Warnings and errors are never treated as success. Every reply in this release requires only a status, so a reply that passes the definition is not, by itself, a success.

A transfer is the one call that changes money, so a reply the example cannot read is never treated as a refusal. A lost reply, a server error or any other success-looking status (the R2026.3.3 sample shows HTTP 200 for Add Transfer, where this release declares 201) means the outcome is **unknown**. The example then says so, never sends again, and blocks new transfers for that customer until the outcome is resolved.

**Not available from Fiserv publicly.** We found no exhaustive list of `TransferType` values, no v11 definition or reply example that confirms how an available balance is read, and no confirmation from a live bank of any value used here. The `Avail` and `Total` labels come from an older official sample collection (R2026.3.3), not from this release. Treat them as Fiserv's own examples, not as a promise about any bank.

Fiserv may publish a corrected release. This example then needs a reviewed update; it will not accept a changed file on its own.

### Honest limits

- **Wire shape, not behaviour.** The mock validates every request and its own replies against the release. That does not tell you how a real Fiserv system answers.
- **No product claim.** These are Fiserv's generic Banking Hub definitions. They do not say which values a particular Fiserv core uses.
- **One mock value is invented.** The release requires an account status code but declares no values for it. The mock sends `FictionalMockStatus`; the client never reads it.
- **Identity is simulated.** One fixed fictional caller. This is not bank sign-in.
- **Older samples for two labels.** `Avail` and `Total` come from Fiserv's official R2026.3.3 sample collection, not from this release (see above).
- **A private journal.** The host keeps a small local journal so an unknown transfer outcome blocks the next transfer, even after a restart. It holds no amount, account or transcript.
- **Not done yet:** a recorded spoken run and response-time measurement.

## Vendor files and versions

- **Vendor release:** Fiserv Banking Hub release 11.0.0.2026.4.1.
- **Release file:** `esf-service-swagger-release-11.0.0.2026.4.1.zip`, about 1.1 MB, from Fiserv's Banking Hub **Resources** page under **API Specification** (**Download API Specifications (v11.0.0.2026.4.1)**).
- **Where it goes:** `vendor-inputs/` inside this folder. The file stays out of Git.
- **Pinned:** this example is pinned to 11.0.0.2026.4.1. It checks the file when it starts and refuses any other file.
- **What it reads:** `bh_demo/contract.py` builds request and response checks from four of Fiserv's release files.
- **Known error in the release:** the transaction definition, `AcctTrnService` 11.0.0 (see [What is happening](#what-is-happening)).
- **Older sample labels:** `Avail` and `Total` come from Fiserv's official Premier sample collection R2026.3.3, not from this release.
- **Runtime:** rasa-pro 3.21.0.dev5, Python 3.12.

The exact files and their hashes are in [VENDOR-FILES.md](VENDOR-FILES.md), and what changed over time is in [CHANGELOG.md](CHANGELOG.md).

## Change it

A small exercise: change a fictional balance in the mock bank and hear the new amount in a reply.

1. Open `bh_demo/mock.py`. Find the `ACCOUNTS` table. The first row, `"5550010001"`, is the account the assistant calls `DDA-A`. Money is kept in cents, so `"avail": 125000` is USD 1,250.00.
2. Change `125000` to another number, for example `99900` (USD 999.00). Save the file.
3. Stop the example with **Ctrl+C** if it is running, then start it again with `DEMO_SEED=0 make run` (the reference data, where this exact amount applies).
4. In the Inspector, ask "What is the balance of DDA-A?". The reply now gives your new amount.
5. Change the number back to `125000` when you are done. The tests and the checked sequence in [Try these conversations](#try-these-conversations) expect USD 1,250.00.

## Troubleshooting

When something is missing, `make run` stops and prints a line that starts with `Not ready.` and says what to fix.

### 1. The release file is missing

The terminal says `Not ready. Vendor definitions not supplied.` and names the file to download.

Fix: do [steps 1 and 3 of Start it](#start-it). The file must be named exactly `esf-service-swagger-release-11.0.0.2026.4.1.zip` and sit in `vendor-inputs/` inside the `fiserv-banking-hub-11.0.0.2026.4.1` folder. Do not unzip it.

### 2. The release file is not the right one

The terminal says `Not ready. The file in vendor-inputs/ is not the expected Fiserv download. Delete it and download it again from the official page.`

Fix: this example is pinned to 11.0.0.2026.4.1 and refuses any other file. Delete the file, then download version 11.0.0.2026.4.1 again from Fiserv's **Resources** page (step 1 of [Start it](#start-it)).

### 3. A secret is missing

The terminal says `Not ready. Add these Codespaces secrets, then rebuild:` followed by the names that are missing.

Fix: add each named secret (`RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`) as described in [What you need](#what-you-need), with **Repository access** set to this repository. Then rebuild the Codespace. The Fiserv mock needs no Fiserv secrets.

### The Inspector link does not open

Wait until the terminal prints `Rasa server is up and running`. If the link still does not open, click the **Ports** tab next to the terminal, find port `5005`, and click the small globe icon on its row.

## Files

### What is inside

| File or folder | What it does |
|---|---|
| `bh_demo/contract.py` | Checks the downloaded ZIP and builds request and response checks from four of Fiserv's release files |
| `bh_demo/mock.py` | The local mock bank: the release's paths and bodies, fictional data, every reply checked against the release |
| `bh_demo/client.py` | Our direct client for four release operations, with Fiserv's success rules and the exact `Avail` and `Total` labels |
| `bh_demo/vendor_models/`, `bh_demo/vendor_api.py`, `make_models.py` | Pydantic models generated from the pinned release for the three operations the client calls (names, types, required fields, allowed values; no vendor descriptions), and the map from each operation to its request and reply model. The client builds requests and reads replies through them |
| `bh_demo/recorded_exchanges.py` | The example's own requests and replies (fictional data), which the models must read and give back unchanged |
| `bh_demo/server.py` | The MCP server the assistant calls: exactly seven tools |
| `bh_demo/host.py` | Identity simulator, permitted reads, the transfer review, one confirmed send, a private journal, and the plain "not available" answers |
| `lib/`, `hooks.py` | Presentation controls: your aliases at the start, no repeated text, and only the host announces a review or an acceptance |
| `skills/banking/` | The assistant's skill and its tool bindings |

### What stays out of this repository

No Fiserv file is stored here: no ZIP, no extracted definition and no copy of its schemas. The generated models in `bh_demo/vendor_models/` hold interface facts only (field names, types, required fields and allowed values for the three operations used), with no descriptions or examples from Fiserv. `vendor-inputs/` is ignored by Git. If the file you supply is not exactly the one this example was written for, it refuses to start rather than guess.

### For developers

```bash
make test           # source, host and server tests; contract tests skip without the release file
make contract-test  # the contract tests (need the release file; skipped without it)
make validate       # Rasa project validation
make models         # regenerate bh_demo/vendor_models/ (needs the release file)
make models-check   # fail if the committed models differ from a fresh generation
```

CI has no Fiserv file, so contract-dependent tests print that they were skipped. A skipped input never qualifies the contract.

A live text check goes through the REST channel with a real model (a few cents, needs the three secrets and the release file). It is not part of `make test`:

```bash
uv run --locked python tests/live_text_check.py
```
