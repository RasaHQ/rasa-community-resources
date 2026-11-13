# Talk to a fictional bank: A Rasa voice demo for Premier 11.0.0_PRM

## What this example shows

Ask for your balance, explore recent transactions, check a loan payment, and request a transfer between your own accounts—all through a conversation. This example connects a Rasa assistant to a **local simulation of Fiserv Banking Hub (Premier)**.

It was tested with the **Fiserv Banking Hub Premier 11.0.0_PRM specifications as downloaded 12 Nov 2026**. See [Vendor files and versions](#vendor-files-and-versions).

> **Demo status:** text conversations have been checked with a real model. A recorded spoken run and response-time measurements are still outstanding. The voice walkthrough below describes the intended experience; the complete microphone-to-spoken-reply path has not yet been verified.
>
> All people, accounts, and amounts are fictional. The voice assistant always uses the local mock, never a real Fiserv banking system. Model and speech services are external, so use only fictional information.

<details>
<summary>Qualification recorded before this walkthrough rewrite</summary>

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, text conversation only (development build)
Assessed by:   Source tests with the real contract, and a live text check in a Codespace
Verified with: Real OpenAPI validators and loopback mock, the pinned Fiserv ZIP, a real model over the REST text channel; spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
Industry:      Banking
You learn:     How to connect a voice assistant to banking tools and confirm a transfer before it is sent.
Catalog name:  Fiserv Premier voice banking demo
```

</details>

You will run it in your browser using GitHub Codespaces. You do not need to install Python on your computer or have credentials for a real bank.

### What you will learn

By running this example, you will see how to:

- Connect a conversational assistant to banking tools.
- Check API requests and successful responses against published definitions.
- Require an explicit confirmation before submitting a transfer.
- Report unavailable information without inventing an answer.
- Handle a lost transfer response without accidentally sending the transfer twice.

You can complete the walkthrough without knowing API definitions or banking terminology. These concepts are explained as you encounter them, with implementation details after the walkthrough.

## What you need

| You need | Why |
|---|---|
| A [GitHub account](https://github.com) with Codespaces access | Runs the example in a cloud development environment |
| A Rasa Developer Edition license | Enables the Rasa runtime |
| An OpenAI API key with available API usage | Gives the assistant access to the language model |
| A Deepgram API key with available API usage | Gives the demo access to speech services |
| Fiserv's `BankingHub_Premier_api_specs.zip` | Supplies the API definitions used to build and check the mock |
| A browser and a working microphone | Lets you use the voice interface |

[rasa.community/keys](https://rasa.community/keys/) explains how to get the license and each key.

**Cost:** the Rasa Developer Edition license is free. Do not assume the entire demo is free: model and speech usage may consume credits or incur charges, and Codespaces has usage allowances. Check your accounts before starting. [ChatGPT and OpenAI API billing are separate](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform). See [GitHub's Codespaces billing guide](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces).

**Time:** total setup time has not yet been measured. Allow extra time for the first environment build and startup.

You do **not** need Fiserv trial API credentials for this walkthrough. The linked Premier specifications download does not require signing in. Trial access and real-bank credentials are separate.

<a id="walkthrough"></a>

### 1. Get your license and API keys

A **license key** enables a product. An **API key** allows this application to use a service through your account. Treat both like passwords.

| Secret name—copy exactly | Where to get its value |
|---|---|
| `RASA_LICENSE` | [Get a free Rasa Developer Edition license](https://rasa.community/keys/#rasa) |
| `OPENAI_API_KEY` | [Create an OpenAI API key and check billing](https://rasa.community/keys/#openai) |
| `DEEPGRAM_API_KEY` | [Create a Deepgram project API key](https://rasa.community/keys/#deepgram) |

Save the values securely. Do not put them in source files, commit them to Git, or paste them into a conversation or issue.

**Checkpoint:** you have all three values. A ChatGPT login alone does not provide an OpenAI API key.

### 2. Add the keys to GitHub Codespaces

A **Codespaces secret** keeps a sensitive value outside the repository. GitHub makes it available to the application as an environment variable—a named setting the program can read.

1. Open your [personal Codespaces settings](https://github.com/settings/codespaces).
2. Under **Secrets**, click **New secret**.
3. Enter `RASA_LICENSE` as the name.
4. Paste only the license value into the value field. Do not add `RASA_LICENSE=` or surrounding quotes.
5. Under **Repository access**, select `RasaHQ/rasa-community-resources`.
6. Save the secret.
7. Repeat for `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`.

Use **Codespaces secrets**, not GitHub Actions secrets. Give each secret access to this repository.

**Checkpoint:** all three names appear in your Codespaces secrets list. Their saved values are hidden; that is expected.

> If you add or change secrets after creating a Codespace, stop and restart the Codespace so it receives the updated values. See [GitHub's secret-management guide](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces).

## Start it

Follow these steps in order. Each step has a checkpoint so you know when to continue. Steps 1 and 2 are in [What you need](#what-you-need).

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-premier-11.0.0-prm/devcontainer.json)

- **Before starting:** save `RASA_LICENSE`, `OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` as personal Codespaces secrets. [Get the keys](https://rasa.community/keys/) and follow [the walkthrough](#walkthrough).
- **Use this badge:** it selects this example's development environment.
- **After the setup log says `READY`:** upload the unopened Premier ZIP into `vendor-inputs/`, then run `make run`.
- **Open the assistant:** wait for `Rasa server is up and running`, then follow the printed Inspector link. The server uses port `5005`.
<!-- codespaces:end -->

This example runs only in GitHub Codespaces, which gives everyone the same tested setup. There are no local setup steps: running it on your own computer is not tested or supported.

### 3. Download Fiserv's API definitions

Do this in a browser on your own computer:

1. Open the [official Premier specifications ZIP](https://developer.fiserv.com/api/download-api-zip/openapi/BankingHub?filename=BankingHub_Premier_api_specs.zip&branch=main). This direct download works without signing in.
2. Save the file as `BankingHub_Premier_api_specs.zip` in your Downloads folder.
3. The [Banking Hub Resources page](https://developer.fiserv.com/product/BankingHub/docs/resources/resources.md?branch=active) lists a newer general bundle with a different filename. Use the Premier ZIP linked above for this example, not that general bundle.
4. Keep the ZIP intact. **Do not extract or repackage it.** If your browser automatically extracts ZIP downloads, retain or download the original ZIP as well.

An **API definition** describes the operations a service exposes and the structure of its requests and responses. This example uses Fiserv's definitions to build a mock and check its messages.

The example was tested with one specific version of the ZIP (see [VENDOR-FILES.md](VENDOR-FILES.md)). Startup compares your download with it using a **hash**, a fingerprint of the file. If Fiserv has changed the download, the example still starts when nothing it uses changed, and says so; if something it uses changed, it stops and names it.

**Checkpoint:** the original `BankingHub_Premier_api_specs.zip` is on your computer, ready to upload. If the portal no longer offers that file, ask the maintainers rather than substituting a different product's specifications.

### 4. Open the example in a Codespace

1. Click the Codespaces badge at the top of this section. That badge selects this example's setup.
2. On the **Create codespace** page, click **Create codespace**.
3. Wait for the browser-based editor to open and finish building the environment. This may take several minutes.
4. Look for `READY` at the end of the setup log.

The **Explorer** is the file-and-folder panel on the left. The **terminal** is the panel where you enter commands. The terminal opens in this example's folder, so you do not need to change directories.

**Checkpoint:** setup has printed `READY` and the terminal is available for input. The environment is prepared; the assistant is not running yet.

### 5. Upload the ZIP into the example

The ZIP is currently on your computer. The application runs in the Codespace, so it needs its own copy.

1. In the Explorer, locate the example folder named `fiserv-premier-11.0.0-prm`. Expand parent folders if necessary.
2. If it already contains a `vendor-inputs` folder, use that folder. Otherwise, right-click `fiserv-premier-11.0.0-prm`, choose **New Folder**, enter `vendor-inputs`, and press **Enter**.
3. Right-click `vendor-inputs` and choose **Upload…**.
4. Select `BankingHub_Premier_api_specs.zip` from your computer's Downloads folder.
5. Wait for the upload to finish.

The file must be at this location **relative to the example folder**:

```text
vendor-inputs/BankingHub_Premier_api_specs.zip
```

**Checkpoint:** you can see the ZIP inside `fiserv-premier-11.0.0-prm` → `vendor-inputs` in the Explorer. Upload the ZIP itself, not its extracted contents, and do not place it in a `vendor-inputs` folder at the repository root.

### 6. Start the assistant

Click in the terminal, paste this command, and press **Enter**:

```bash
make run
```

`make` runs a task defined by the project. The `run` task starts this demo. During startup, the application checks the ZIP and builds the local mock from the definitions it contains.

Look for:

```text
Vendor definitions: found and checked
```

Then find the line beginning:

```text
Open the Inspector:
```

The link after it opens the assistant's test interface. Leave this terminal running. A server keeps running rather than immediately returning to a command prompt; that is normal.

**Checkpoint:** wait for `Rasa server is up and running` before opening the Inspector. The link prints before the server is ready. If it prints `Not ready.`, fix the reported missing item before continuing. If the hash check fails, do not disable it or change the expected hash.

### 7. Open the Inspector and choose text or speech

1. Hold **Ctrl** (or **Command** on a Mac) and click the Inspector link in the terminal.
2. If it does not open, select the editor's **Ports** tab, find port `5005`, and click its globe icon.
3. When your browser requests microphone access, choose **Allow**.

For a text conversation, click **Type your message**, type the prompt, and press **Enter**. This lets you continue without a microphone. A typed check does not verify speech.

The **Inspector** is the browser interface for trying the assistant. A **port** is a numbered endpoint for a running service; this demo uses `5005`.

Use only fictional information. The speech provider receives your audio. The intended speech output uses a single synthetic voice.

**Checkpoint:** the Inspector is open and microphone permission is allowed. If no permission prompt appears or you cannot start a voice conversation, use [Troubleshooting](#troubleshooting). The spoken path is still awaiting verification.

### 10. Stop and clean up

Do this when you have finished [trying the conversations](#try-these-conversations):

1. Click the terminal running the server and press **Ctrl+C**, including on a Mac. The server stops and the terminal returns to a prompt.
2. Open [your Codespaces](https://github.com/codespaces).
3. Save or commit any appropriate work you want to keep before deleting the environment. Never commit secrets or vendor files.
4. Find this Codespace, open its three-dot menu, and choose **Delete** if you no longer need it.

Ctrl+C stops the application, not the Codespace. Stopping a Codespace ends its compute usage, but retained storage still counts toward storage usage. Deleting it removes its local files, including the uploaded ZIP and demo journal.

## Try these conversations

**Your first goal:** open the assistant and ask, “What is my checking balance?” With the initial demo data, the expected answer is **USD 1,250.00 available**.

Then type or say these, one at a time:

- What is my checking balance?
- What accounts do I have?
- What did I spend recently?
- What is my next loan payment?
- What is my loan payoff?
- Verify me.
- Move 25 dollars from checking to bills.
- Confirm transfer.

### The full checked sequence

#### 8. Ask your first questions

The demo already has one fictional customer. You do not need to create a bank account or sign in as a bank customer.

Start with:

> What is my checking balance?

With the initial mock data, the expected answer is **USD 1,250.00 available**. Then try these prompts, one at a time. Wait for each reply before speaking again.

Wording may vary. Check the facts rather than expecting an exact sentence.

| Say | Expected information | What you are testing |
|---|---|---|
| “What accounts do I have?” | `checking-A`, `bills-A`, and `loan-A` | Finding the fictional customer's accounts |
| “What did I spend recently?” | Up to three recent **posted** transactions, described as the returned transactions | Reporting the available history without claiming it is complete |
| “What is my next loan payment?” | **USD 182.40**, due **December 1, 2026** | Reading the next installment and due date |
| “What is my loan payoff?” | Current payoff: **USD 4,120.55** | Reading the supplied current payoff |
| “What is my loan payoff on December 20, 2026?” | A dated quote is unavailable; the assistant offers the current payoff instead | Declining an unsupported request without inventing a future amount |

A **posted transaction** has been recorded to the account. A **loan payment** is an installment. A **payoff** is the amount to settle the loan. The demo supplies a current payoff, not a quote for an arbitrary future date.

The dates and amounts above are fixed demo data; they do not automatically track today's date. `bills-A` is another account owned by the fictional customer, not an external biller. This demo does not include savings accounts.

#### 9. Try a transfer with explicit confirmation

Follow this sequence without inserting another message between the transfer review and confirmation:

| Step | Say | Expected behavior |
|---|---|---|
| 1 | “Verify me.” | The assistant reports that simulated verification was refreshed. It lasts about a minute. |
| 2 | “Move 25 dollars from checking to bills.” | The assistant reads back the exact transfer and asks you to say `confirm transfer`. |
| 3 | “Confirm transfer.” | The assistant reports `accepted` and explains that accepted does not mean posted. |

**Verification is simulated.** Saying “Verify me” is a demo shortcut, not a way to authenticate a real bank customer.

**Accepted is not posted.** The request was acknowledged; this is not proof that a bank has completed the transfer and updated its ledger.

Try these additional checks:

| Try | Expected behavior |
|---|---|
| Request another transfer, then say something other than `confirm transfer` immediately after its review | The review is canceled and the transfer is not sent |
| Ask for another person's account, such as `checking-B` | Access is refused |
| Attempt a transfer after verification expires | If refused for stale verification, say “Verify me,” then request the transfer again |

If a transfer result is **unknown**, do not repeatedly submit the transfer or delete the journal. The demo blocks further transfers for that caller because it cannot establish what happened. Developers can explore this deliberately using [the lost-response exercise](#optional-exercise-a-lost-transfer-response).

When you finish, follow [10. Stop and clean up](#10-stop-and-clean-up).

## What is happening

The assistant handles the conversation. The host code controls whether a transfer can be sent. A local mock supplies fictional bank data.

```text
You (Inspector, voice or text)
  -> Rasa + language model          understands you and replies
  -> MCP server (seven tools)       the tools the assistant can call
  -> Host policy and journal        decides if a transfer may be sent
  -> Banking Hub client             builds the banking requests
  -> Local Premier mock             answers with fictional data,
                                    checked against Fiserv's API definitions
```

| Component | Role |
|---|---|
| Inspector and speech services | Provide the voice interaction |
| Rasa and the language model | Interpret requests and produce conversational replies |
| Model Context Protocol (MCP) server | Exposes seven banking tools the assistant can call |
| Host policy and journal | Check transfer conditions and retain transfer state |
| Banking Hub client | Builds requests for the supported banking operations |
| Local Premier mock | Handles requests using fictional data |
| Downloaded API definitions | Define the allowed request and response structures |

**Model Context Protocol (MCP)** provides the tool interface used here. **OpenAPI** is the format of the API definitions. A **contract validator** checks that a message follows those definitions. **Loopback** means the client talks to a mock in the same development environment, rather than over a connection to a bank.

The normal voice demo uses external model and speech services, but its banking requests stay local. The optional Fiserv trial in [Change it](#change-it) is a separate, manual workflow.

### Transfer safeguards

The assistant has a Rasa-side trigger called `banking_submit_transfer`. It takes no arguments, is not an MCP tool, and cannot authorize a transfer by itself. The host sends only after it has seen the next raw user turn say exactly `confirm transfer`.

The **journal** is a durable record of transfer state. If a transfer response is lost, the request may have been accepted even though the caller did not receive an answer. Retrying could submit it twice. The demo therefore does not resend and blocks new transfers for the caller across application restarts.

The journal lives in `var/private/`. It records a caller, opaque review ID, state, and **epoch**—an identifier for the fictional exercise. It never stores an amount, account, or transcript.

### What has been verified—and what has not

The transfer reply controls have source tests. A fresh end-to-end run of this revised walkthrough is still outstanding.

| Item | Recorded status |
|---|---|
| Author | Rasa Community contributors |
| Assessment date | November 12, 2026 |
| Environment | `rasa-pro 3.21.0.dev5`, Python 3.12; development build |
| Source and contract checks | Source tests with the real contract, OpenAPI validators, pinned Fiserv ZIP, and loopback mock |
| Conversation check | Live text check in a Codespace with a real model through the REST channel |
| Spoken conversation | Recorded microphone-and-speech-output run still outstanding |
| Response time and setup duration | Not yet measured |
| Scripted native test without a live model | Still outstanding |
| Real Premier integration | Not established by this mock or its tests |

### Limits to understand before adapting the demo

- **Valid structure does not prove real-bank behavior.** Contract checks verify message formats, not how a real Premier installation responds.
- **Error responses are an exception to schema validation.** The published default response requires success fields, so errors cannot satisfy it. The mock emits a small status-only error; the client treats non-success status as unavailable. Do not describe these errors as schema-validated responses.
- **Identity is simulated.** One fixed fictional caller is used. This is not bank sign-in.
- **Coverage is limited.** Savings accounts and dated payoff quotes are not supported.
- **Accepted is not posted.** A valid acceptance response does not establish completed posting.
- **Unknown remains unknown.** A lost transfer response is not retried. Resetting the fictional exercise preserves the unresolved history.
- **The trial is separate.** It is manual and read-only. The voice assistant always uses the mock.

## Vendor files and versions

This example was tested with the **Fiserv Banking Hub Premier 11.0.0_PRM specifications as downloaded 12 Nov 2026**. [VENDOR-FILES.md](VENDOR-FILES.md) lists the exact files and what the example checks if your download differs. [CHANGELOG.md](CHANGELOG.md) records what changed in each version and in the example.

If the start-up says Fiserv changed something this example uses, it names it. Your download is newer than this example; please open an issue.

### Which version do I need?

This example targets the Premier-specific `11.0.0_PRM` definitions in `BankingHub_Premier_api_specs.zip`. The newer general Banking Hub release `11.0.0.2026.4.1` has different response structures and is not a replacement input for this folder. Use the API definitions required by your bank.

## Change it

### Optional exercise: A lost transfer response

This developer exercise demonstrates why an uncertain result must not be retried automatically.

1. Stop the running demo with **Ctrl+C**.
2. From the example folder, start it with the fault enabled:

   ```bash
   uv run --locked python run_demo.py --fault transfer-response-lost
   ```

3. Open the Inspector using the startup link and follow the verification, transfer-review, and confirmation sequence from [the full checked sequence](#9-try-a-transfer-with-explicit-confirmation).
4. In this simulated fault, the transfer succeeds in the mock but its response is lost. The caller cannot establish that outcome, so the journal retains uncertainty and blocks new transfers. It does not resend.
5. Stop the demo with **Ctrl+C** before resetting the exercise.

To begin a new fictional exercise:

```bash
uv run --locked python -m premier_demo.reset_fixture --reason "starting over" --acknowledge-unresolved
```

This command only works while the example is stopped. It writes an audit row, preserves the old unknown outcome in history, and starts a new exercise. The acknowledgment explicitly accepts that the old result remains unresolved; the reset does not classify it as failed or successful.

Restart normally with:

```bash
make run
```

This is a reset of a fictional exercise, not a recovery procedure for a real bank transfer.

### Optional: Try the Fiserv trial environment

**Skip this section for your first run.** It is for developers who already have Fiserv Banking Hub trial access. It makes real read-only calls to the Premier trial environment, not to a production bank. It does not move money or switch the voice assistant away from the mock.

#### Prepare trial credentials and a call budget

Add these additional **Codespaces secrets**, with access to this repository:

| Secret | Value to supply |
|---|---|
| `FISERV_BH_API_KEY_NAME` | Your trial API key name |
| `FISERV_BH_API_KEY` | Your trial API key |
| `FISERV_BH_API_SECRET` | Your trial API secret |

Stop and restart the Codespace after adding secrets.

You also need a fresh **budget file** specifying the permitted trial calls:

```text
var/private/manual-trial-budget.json
```

Read `premier_demo/quota.py` for the required JavaScript Object Notation (JSON) fields and construct the file from those requirements. Do not guess field names. The budget is separate from the credentials; credentials belong in secrets, not in the budget file.

Without all three credentials and a fresh budget, the trial command refuses to run. The mock is unaffected.

#### Import the budget and make the read

From the example folder, import your budget:

```bash
uv run --locked python -m premier_demo.trial import-budget var/private/manual-trial-budget.json --runner my-codespace
```

Then adapt this command to your trial:

```bash
uv run --locked python -m premier_demo.trial read --runner my-codespace --trial my-trial --period 2026-11 --party YOUR_PARTY_ID
```

Before running it:

- Use the same `--runner` value for budget import and the read.
- Replace `my-trial` with the appropriate trial identifier.
- Use the period matching your budget; `2026-11` is the example's November 2026 value.
- Replace `YOUR_PARTY_ID` with a party identifier from your trial data. Do not type an angle-bracket placeholder into the shell.

#### Understand the trial result

Each run obtains one token using HTTP Basic authentication, then makes at most three core calls. Calls are counted in a local ledger before they are sent and spaced at least seven seconds apart. Secrets are read from the environment and never printed.

The trial's “no records” answer is a status-only response that the published schema does not allow. The trial client reports this as **“no records match”** rather than claiming successful schema validation.

A trial response is evidence about that trial call. It is not production validation or certification of the assistant.

## Troubleshooting

The three most common problems:

1. **`Not ready.` reports a missing vendor file.** Check the exact filename and location: `vendor-inputs/BankingHub_Premier_api_specs.zip` inside this example.
2. **A secret is missing.** Check its exact name, Codespaces settings, and repository access. Stop and restart the Codespace after adding or changing secrets.
3. **The Inspector does not open.** Confirm that `make run` is still running. Try the globe icon for port `5005` in the **Ports** tab.

### All problems and fixes

| What you see | What to check or do |
|---|---|
| The environment has not printed `READY` | Wait for the build. If it reports an error, record that error before entering more commands. |
| You cannot find the Premier ZIP on the Fiserv portal | Check that you are viewing Banking Hub's Premier specifications. If the download has changed, ask the maintainers. |
| `make` cannot find the requested task | Check that you used this README's badge and that your terminal is in the example folder. |
| `Not ready.` reports a missing vendor file | Check the exact filename and location: `vendor-inputs/BankingHub_Premier_api_specs.zip` inside this example. |
| Startup says Fiserv changed something this example uses | Your download is newer than this example. Keep it intact and open an issue; renaming or repackaging it will not help. |
| A secret is missing | Check its exact name, Codespaces settings, and repository access. Stop and restart the Codespace after adding or changing secrets. |
| A provider reports authentication or quota errors | Check the key and available usage in that provider's dashboard. Do not print or share the key. |
| The Inspector does not open | Confirm that `make run` is still running. Try the globe icon for port `5005` in the **Ports** tab. |
| You cannot use the microphone | Check the browser's site microphone permission and selected input device. Record visible errors if voice still fails. |
| A transfer is refused because verification expired | Say “Verify me,” then request and confirm the transfer again. |
| Transfers remain blocked after an unknown result | This is intentional. Use the documented fictional-exercise reset only after stopping the demo; do not delete the journal. |
| An answer is slow | Record the approximate delay and fictional prompt. Response time has not yet been measured. |

When asking for help, include the step number, command or fictional prompt, expected result, and actual error. Remove keys and private information from logs or screenshots.

## Files

### Explore the code

| File or folder | What to look for |
|---|---|
| `skills/banking/` | The assistant's banking instructions and tool bindings |
| `premier_demo/server.py` | The MCP server's seven tools |
| `premier_demo/host.py` | Simulated identity, transfer review, confirmation, one send, and the durable journal |
| `premier_demo/client.py` | The direct Banking Hub client for five operations |
| `premier_demo/mock.py` | Fiserv's paths and message bodies with fictional data |
| `premier_demo/contract.py`, `premier_demo/recorded_exchanges.py` | ZIP verification, request/response checks built from Fiserv's files, and the recorded traffic checked against a newer download |
| `premier_demo/vendor_models/`, `premier_demo/vendor_api.py`, `make_models.py` | Pydantic models generated from the five pinned Fiserv definitions (names, types, required fields, allowed values; no vendor descriptions), and the map from each definition to its request and reply model. The client builds requests and reads replies through them |

### Supported banking operations

Five client operations support the conversation. They are distinct from the seven MCP tools exposed to the assistant.

| Operation | Purpose |
|---|---|
| Accounts by party | Find accounts for the fictional customer; “party” is the API's customer/entity identifier |
| Account: checking | Read the available balance |
| Account: loan | Read the next payment and current payoff |
| Account transactions | Read the returned transaction history |
| Immediate own-account funds transfer | Request a transfer between the customer's own accounts |

The checking and loan operations share a path in Fiserv's files but have different message structures. The implementation keeps them separate by definition document.

Only checking-type **DDA (demand deposit account)** and loan definitions are pinned. Savings accounts and dated payoff quotes are not included.

### Files that stay out of Git

No Fiserv ZIP, extracted definition, or copied schema is included in this repository. Download the original ZIP yourself.

- `vendor-inputs/` holds the vendor input and is ignored by Git.
- `var/private/` holds private runtime state, including the journal, and is ignored by Git.
- A changed vendor ZIP requires a reviewed update to the pinned version. The application refuses an unexpected file rather than guessing whether it is compatible.

### Run the checks

Run these commands from the example folder in a terminal that is not occupied by the running server.

```bash
make test
```

Runs source and mock tests. Tests that require the Fiserv file skip if it is missing.

To regenerate the models after a vendor update (needs the pinned ZIP in `vendor-inputs/`), run `make models`; `make models-check` fails if the committed models differ from a fresh generation. The generator, datamodel-code-generator, is installed only for these two commands.

```bash
make contract-test
```

Runs contract tests against the supplied Fiserv definitions. These also skip without the ZIP. **A skipped test is not evidence that the contract works.** Upload the expected ZIP and inspect the test output for skips.

```bash
make validate
```

Validates the Rasa project configuration. This is separate from running a conversation.

Continuous integration (CI)—the repository's automated checks—does not have the Fiserv ZIP, so contract-dependent tests there report that they were skipped.

For a live text conversation check:

```bash
uv run --locked python tests/live_text_check.py
```

This uses a real model through the representational state transfer (REST) text channel: a hypertext transfer protocol (HTTP) interface rather than the microphone. `uv run --locked` uses the project's locked dependency versions.

It needs all three demo secrets and the Fiserv ZIP, consumes API usage, and is not included in `make test`. Passing it does not verify speech recognition, spoken replies, or voice latency.
