# Talk to a fictional bank: a Rasa voice demo with a SilverLake mock

## What this example shows

Ask for your balance, explore recent transactions, and request a transfer between your checking and savings accounts—all through a conversation. This example connects a Rasa assistant to a **local simulation of the Jack Henry SilverLake core through the jXchange banking API**. It was tested with the **Jack Henry jXchange TPG R2026.1.00 XSD archive as published 3 Nov 2026**; see [Vendor files and versions](#vendor-files-and-versions).

> **Demo status:** text conversations have been checked with a real model. A recorded spoken run and response-time measurements are still outstanding. The voice walkthrough below describes the intended experience; it is not a claim that the full voice path has been verified.
>
> All people, accounts, and amounts are fictional. No request goes to a real bank. The language-model and speech services are external services, so use only fictional information.

<details>
<summary>Qualification recorded before this walkthrough rewrite</summary>

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, text conversation only (development build)
Assessed by:   Source tests with the real schemas, and a live text check in a Codespace
Verified with: The pinned jXchange archive, schema validation of every SOAP body, a real model over the REST text channel; spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
Industry:      Banking
You learn:     How to connect a voice assistant to banking tools and check requests against a published API format.
Catalog name:  Jack Henry SilverLake voice banking demo
```

</details>

You will run it in your browser using GitHub Codespaces. You do not need to install Python on your computer or have a Jack Henry account.

**Your first goal:** open the assistant and ask, “What is my checking balance?” With the reference demo data (start with `DEMO_SEED=0 make run`), the expected answer is **USD 1,250.00 available**.

### What you will learn

By running this example, you will see how to:

- Connect a conversational assistant to banking tools.
- Check that requests and responses follow a published API format.
- Require an explicit confirmation before submitting a transfer.
- Handle missing information and uncertain transfer outcomes without guessing.

You can follow the walkthrough without knowing banking protocols or the tools used here. Those terms are explained after your first conversation.

### The other Jack Henry example

For the other Jack Henry API, see the separate [Symitar-in-Platform example](../jack-henry-symitar/). Its representational state transfer (REST) API uses different definitions from SilverLake's jXchange.

## What you need

How to get each key is explained at [rasa.community/keys](https://rasa.community/keys/).

| You need | Why |
|---|---|
| A [GitHub account](https://github.com) with Codespaces access | Runs the example in a cloud development environment |
| A Rasa Developer Edition license | Enables the Rasa runtime |
| An OpenAI API key with available API usage | Gives the assistant access to the language model |
| A Deepgram API key with available API usage | Gives the demo access to speech services |
| A browser and a working microphone | Lets you use the voice interface |

**Cost:** the Rasa Developer Edition license is free. Do not assume the entire demo is free: OpenAI and Deepgram usage may consume credits or incur charges, and Codespaces has usage allowances. Check your accounts before starting. [ChatGPT and OpenAI API billing are separate](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform). See [GitHub's Codespaces billing guide](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces).

**Time:** one recorded fresh setup reached the running server in about six minutes, including harness corrections. That is not a typical setup estimate. Allow extra time for the first environment build and schema loading.

<a id="walkthrough"></a>

### 1. Get your license and API keys

A **license key** enables a product. An **API key** lets this application use a service through your account. Treat these values like passwords.

| Secret name—copy exactly | Where to get its value |
|---|---|
| `RASA_LICENSE` | [Get a free Rasa Developer Edition license](https://rasa.community/keys/#rasa) |
| `OPENAI_API_KEY` | [Create an OpenAI API key and check billing](https://rasa.community/keys/#openai) |
| `DEEPGRAM_API_KEY` | [Create a Deepgram project API key](https://rasa.community/keys/#deepgram) |

Save each value securely. Do not put keys in source files, commit them to Git, or paste them into a conversation or issue.

**Checkpoint:** you have all three values. Having a ChatGPT login alone does not provide an OpenAI API key.

### 2. Add the keys to GitHub Codespaces

A **Codespaces secret** stores a sensitive value outside the repository. GitHub makes it available to the running application as an environment variable—a named setting the program can read.

1. Open your [personal Codespaces settings](https://github.com/settings/codespaces).
2. Under **Secrets**, click **New secret**.
3. Enter `RASA_LICENSE` as the name.
4. Paste only the license value into the value field. Do not add `RASA_LICENSE=` or surrounding quotes.
5. Under **Repository access**, select `RasaHQ/rasa-community-resources`.
6. Save the secret.
7. Repeat for `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`.

These are **Codespaces secrets**, not GitHub Actions secrets. Each secret needs access to this repository.

**Checkpoint:** all three names appear in your Codespaces secrets list. GitHub hides their saved values; that is expected.

> Already created a Codespace? After adding or changing a secret, stop and restart the Codespace so it receives the updated value. See [GitHub's secret-management guide](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces).

## Start it

This example runs only in GitHub Codespaces, which gives everyone the same tested setup. There are no local setup steps: running it on your own computer is not tested or supported.

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-jack-henry-silverlake/devcontainer.json)

- **Before starting:** save `RASA_LICENSE`, `OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` as personal Codespaces secrets. [Get the keys](https://rasa.community/keys/) and follow [the walkthrough](#walkthrough).
- **Use this badge:** it selects this example's development environment.
- **After the setup log says `READY`:** run `make download` and wait for `Saved and checked`, then run `make run`.
- **Open the assistant:** wait for `Rasa server is up and running`, then follow the printed Inspector link. The server uses port `5005`.
<!-- codespaces:end -->

Follow these steps in order. Each step includes a checkpoint so you know when to continue. Steps 1 and 2 are in [What you need](#what-you-need).

### 3. Open the example

1. Click the Codespaces badge above. Use that badge so GitHub selects this example's setup.
2. On the **Create codespace** page, click **Create codespace**.
3. Wait for the browser-based editor to open and the environment to finish building.
4. Look for `READY` at the end of the setup log.

The **terminal** is the panel where you enter commands. It opens in this example's folder. You do not need to change directories.

**Checkpoint:** setup has printed `READY` and the terminal is available for input. This means the environment is prepared; the banking assistant is not running yet.

### 4. Download the banking API definitions

In the terminal, paste this command and press **Enter**:

```bash
make download
```

`make` runs a task defined by the project. Here, the `download` task fetches Jack Henry's public schema archive into `vendor-inputs/` and checks that it matches the version expected by this example.

A **schema** describes the allowed structure of an API message: which fields it can contain and what types of values they accept. Think of it as a form with rules for filling in each field.

**Checkpoint:** the terminal prints `Saved and checked`.

If the download or check fails, do not continue or substitute a different archive. Read the error and use [Troubleshooting](#troubleshooting).

### 5. Start the assistant

Run:

```bash
make run
```

The first start takes longer while the schemas load. Look for:

```text
Vendor definitions: found and checked
```

Then find the line beginning:

```text
Open the Inspector:
```

The link after it opens the assistant's test interface. **Leave this terminal running.** It may continue printing messages instead of returning to a command prompt; that is normal while the server runs.

**Checkpoint:** wait for `Rasa server is up and running` before opening the Inspector. The link prints before the server is ready; opening it immediately can fail. If you see `Not ready.`, fix the reported missing item before continuing.

### 6. Open the Inspector and choose text or speech

1. Hold **Ctrl** (or **Command** on a Mac) and click the Inspector link in the terminal.
2. If it does not open, select the editor's **Ports** tab, find port `5005`, and click its globe icon to open it in your browser.
3. When the browser requests microphone access, choose **Allow**.

For a text conversation, click **Type your message**, type the prompt, and press **Enter**. This lets you continue without a microphone. A typed check does not verify speech.

The **Inspector** is the browser interface for trying the assistant. A **port** is a numbered endpoint for a running service; `5005` is the one used by this demo.

Use only fictional information. The speech provider receives your audio.

**Checkpoint:** the Inspector is open and microphone permission is allowed. If no microphone prompt appears or you cannot start a voice conversation, use the troubleshooting section; the spoken path is still awaiting verification.

### Stop and clean up

When you finish:

1. Click the terminal running the server and press **Ctrl+C**, including on a Mac. The server stops and the terminal returns to a prompt.
2. Open [your Codespaces](https://github.com/codespaces).
3. If you want to keep your work, save or commit appropriate changes before deleting the environment. Never commit secrets or downloaded vendor files.
4. Find this Codespace, open its three-dot menu, and choose **Delete** if you no longer need it.

Stopping the application with Ctrl+C does not stop the Codespace. Stopping a Codespace ends its compute usage, but retained storage still counts toward storage usage. Deleting it removes its local files, including the demo journal.

## Try these conversations

The demo already has one fictional customer. You do not need to create a bank account or sign in as a bank customer. Type or say these lines one at a time, and wait for each reply:

- “What is my checking balance?” (expected: **USD 1,250.00 available**)
- “What accounts do I have?”
- “What did I spend recently?”
- “What is my next loan payment?”
- “What is my loan payoff on November 20, 2026?”
- “Verify me.”
- “Move 25 dollars from checking to savings.”
- “Confirm transfer.”

The wording may vary. Check the facts in the answer rather than expecting an exact sentence.

Each start uses different fictional balances, loan amounts and transactions, so the amounts you hear can differ from the ones on this page. The first line that `make run` prints shows the seed, for example `Demo data seed: 4821; set DEMO_SEED=4821 to get the same data again.` Start with `DEMO_SEED=4821 make run` to get that same data again. To follow the checked sequence below exactly, start with the reference data:

```bash
DEMO_SEED=0 make run
```

### The full checked sequence

Start with:

> What is my checking balance?

With the initial mock data, the expected answer is **USD 1,250.00 available**. Then try the following, one at a time. Wait for each reply before speaking again.

| Say | Expected information | What you are testing |
|---|---|---|
| “What accounts do I have?” | `checking-A`, `savings-A`, and `loan-A` | Finding the fictional customer's accounts |
| “What did I spend recently?” | Up to three recent transactions, described as the returned transactions | Reporting the available history without claiming it is complete |
| “What is my next loan payment?” | Current payment due: **USD 242.40**. Next due date: **December 1, 2026** | Keeping the amount due and the next due date as separate facts |
| “What is my loan payoff on November 20, 2026?” | **USD 4,120.55** for that date | Looking up a supplied, date-specific payoff quote |
| “What is my loan payoff on December 24, 2026?” | No quote is supplied for that date | Admitting missing information instead of calculating an answer |

A **loan payment** is an installment. A **payoff quote** is the amount quoted to settle the loan on a particular date. They are different questions.

The dates above are fixed demo fixtures. Keep the stated dates when testing these examples; they are not automatically updated to today's date.

### Try a transfer with explicit confirmation

This example supports immediate transfers between the fictional customer's own checking and savings accounts.

Follow this sequence without inserting another message between the transfer review and confirmation:

| Step | Say | Expected behavior |
|---|---|---|
| 1 | “Verify me.” | The assistant reports that simulated verification was refreshed. It lasts about a minute. |
| 2 | “Move 25 dollars from checking to savings.” | The assistant reads back the exact transfer and asks you to say `confirm transfer`. |
| 3 | “Confirm transfer.” | The assistant reports `accepted` and explains that accepted does not mean posted. |

**Verification is simulated:** saying “Verify me” is a demo shortcut, not a way to authenticate a real bank customer.

**Accepted is not posted:** the mock has acknowledged the request. This is not proof that a real bank has completed a transfer or updated its ledger.

Try these additional checks:

| Try | Expected behavior |
|---|---|
| Request another transfer, then say something other than `confirm transfer` immediately after the review | The review is canceled and the transfer is not sent. Request a new review before any new confirmation |
| Ask for another person's account, such as `checking-B` | The assistant refuses access |
| Attempt a transfer after verification expires | If refused for stale verification, say “Verify me,” then request the transfer again |

If a transfer result is **unknown**, do not repeatedly submit it or delete the journal to clear the block. The example deliberately holds further transfers for that caller because it cannot establish what happened. See [Transfer safeguards](#transfer-safeguards).

## What is happening

The assistant understands the conversation, but code controls which banking operations can be sent. The bank itself is simulated inside the development environment.

```text
You (Inspector: text or voice)
  -> Rasa and the language model     understand the request, write the reply
  -> MCP server                      exposes the banking tools
  -> Host policy and journal         decide if a transfer is allowed, remember its state
  -> jXchange client                 builds the banking API messages
  -> Local SilverLake mock           answers with fictional data, checked against the downloaded schemas
```

| Component | Its role |
|---|---|
| Inspector and speech services | Provide the voice interaction |
| Rasa and the language model | Interpret requests and produce conversational replies |
| Model Context Protocol (MCP) server | Exposes banking tools the assistant can call |
| Host policy and transfer journal | Check whether a transfer is allowed and remember its state |
| jXchange client | Builds requests in the banking API's message format |
| Local SilverLake mock | Handles requests using fictional banking data |
| Downloaded schemas | Validate the structure of request and response bodies |

**Model Context Protocol (MCP)** is the interface used here to expose tools to the assistant. **jXchange** is the banking interface used by this example. It uses **simple object access protocol (SOAP)** to exchange messages written in **extensible markup language (XML)**. **Web Services Description Language (WSDL)** files describe service operations; this example reads their SOAPAction values to identify the requested operations.

The banking connection stays local to the Codespace. The demo still uses external model and speech services and downloads the public schema archive.

### Transfer safeguards

A transfer review is not permission to send money indefinitely. The host requires the next raw user turn to say `confirm transfer` before it sends the reviewed request. An unrelated next message cancels that review.

The assistant also has a Rasa-side trigger named `banking_submit_transfer`. It is **not an MCP tool** and cannot authorize a transfer by itself. The host enforces the confirmation rule.

The **journal** is a persistent record of transfer state. If a transfer response is lost, the request might have been accepted even though the client did not receive the answer. Automatically retrying could submit it twice. This example does not resend and holds new transfers for that caller, including across application restarts.

### What has been verified—and what has not

The transfer reply controls have source tests. A fresh end-to-end run of this revised walkthrough is still outstanding.

| Item | Recorded status |
|---|---|
| Author | Rasa Community contributors |
| Assessment date | November 12, 2026 |
| Environment | `rasa-pro 3.21.0.dev5`, Python 3.12; development build |
| Source and schema checks | Source tests using the published schemas |
| Conversation check | Live text check in a Codespace using a real model through the REST channel |
| Request and response validation | SOAP bodies validated against the pinned jXchange definitions |
| Spoken conversation | Recorded run still outstanding |
| Response time | Not yet measured |
| Setup duration | One recorded setup took about six minutes, including harness corrections; not a typical estimate |
| Real SilverLake integration | Not tested; requires a bank, an agreement, and credentials |

### Limits to understand before adapting this demo

- **Valid structure does not prove real-bank compatibility.** A schema-valid message follows the published format. It does not establish how a real SilverLake system behaves or which fields a particular loan type supports.
- **Identity is simulated.** There is one fixed fictional caller. This is not bank sign-in or production identity verification.
- **Acceptance is not completion.** `RsStat` Success means the request was accepted, not that it was posted.
- **Missing data stays missing.** The assistant reports a supplied payoff quote; it does not invent one for an unsupported date.
- **A fault can leave a transfer outcome unknown.** The mock returns SOAP faults, such as the zero-amount error `100199`. For transfers, only a Client fault or documented business error `100199` or `400001` establishes refusal. Any other fault after sending is an unknown outcome and is never resent. For reads, a fault means the information is unavailable.
- **One optional security schema is excluded.** The archive's XML-signature schema declares a document type definition (DTD) entity, which the loader refuses to process. That namespace remains unresolved; none of the six demonstrated operations needs it.
- **Unknown transfer results require care.** The journal blocks further transfers for the caller after an uncertain result. An audited reset command remains outstanding.

Use this example to learn the conversation flow, integration structure, and transfer controls. A real banking deployment needs further integration work and validation beyond the checks recorded here.

## Vendor files and versions

This example was tested with the **Jack Henry jXchange TPG R2026.1.00 XSD archive as published 3 Nov 2026**. [VENDOR-FILES.md](VENDOR-FILES.md) lists the exact files and what the example checks if your download differs. [CHANGELOG.md](CHANGELOG.md) records what changed in each version and in the example.

If the start-up says Jack Henry changed something this example uses, it names it. Your download is newer than this example; please open an issue.

## Change it

A small exercise: add a payoff quote for a new date and see it in a reply.

1. Open `silverlake_demo/mock.py`. Find the fictional loan account `7001001` in `ACCOUNTS`. Its `payoff` entry maps dates to amounts in cents: `{"2026-11-20": 412055, "2026-12-01": 413390}`.
2. Add a new date, for example `"2026-12-15": 415000`. Do not change the `2026-11-20` value: the start-up check and the tests expect it.
3. Stop the server with **Ctrl+C** and run `DEMO_SEED=0 make run` (the reference data, where this exact amount applies).
4. Ask: “What is my loan payoff on December 15, 2026?” The answer should now be **USD 4,150.00**.
5. Undo your change when you finish. Do not use December 24, 2026; the tests expect that date to have no quote.

## Troubleshooting

The three most common problems:

1. **`Not ready.`** Follow the application's message. Common causes are missing files in `vendor-inputs/` or missing Codespaces secrets.
2. **A secret is missing even though you saved it.** Check its exact name, repository access, and that it is a Codespaces secret. Stop and restart the Codespace after changes.
3. **`make download` fails or does not print `Saved and checked`.** Read the download/check error. Do not disable verification or replace the expected archive with an arbitrary version.

### All problems and fixes

| What you see | What to check or do |
|---|---|
| The environment has not printed `READY` | Wait for the build to finish. If it reports an error, record that error before trying more commands. |
| `make` cannot find the requested task | Check that you used this README's badge and that the terminal is in the example folder. The general Codespaces picker may select a different setup. |
| `make download` fails or does not print `Saved and checked` | Read the download/check error. Do not disable verification or replace the expected archive with an arbitrary version. |
| `Not ready.` | Follow the application's message. Common causes are missing files in `vendor-inputs/` or missing Codespaces secrets. |
| A secret is missing even though you saved it | Check its exact name, repository access, and that it is a Codespaces secret. Stop and restart the Codespace after changes. |
| A provider reports an authentication or quota error | Check the key and available usage in that provider's dashboard. Do not print or share the key. |
| The Inspector link does not open | Confirm that `make run` is still running. Try the globe icon for port `5005` in the **Ports** tab. |
| You cannot use the microphone | Check the browser's site microphone permission and your selected input device. Record any visible error if voice still fails. |
| A transfer is refused because verification expired | Say “Verify me,” then request and confirm the transfer again. |
| Transfers remain blocked after an unknown result | This is an intentional journal safeguard. Ask the maintainers; an audited journal reset command is not available yet. |
| A response is slow | Record the approximate delay and which prompt you used. Latency has not yet been measured. |

If a reply suggests confirming again after cancellation, request a new transfer review first. An old confirmation cannot authorize a new review.

### Getting help

If you need help, report the step number, command or fictional prompt, expected result, and actual error. Remove keys and private information from logs or screenshots before sharing them.

## Files

### Explore the code

After the walkthrough, use this map to find the relevant implementation:

| File or folder | What to look for |
|---|---|
| `skills/banking/` | The assistant's banking instructions and tool bindings |
| `silverlake_demo/server.py` | The MCP server's seven tools |
| `silverlake_demo/service.py` | How the host policy and journal connect to the client |
| `host.py`, `journal.py` | Verification requirements, transfer review, next-turn confirmation, and durable state |
| `silverlake_demo/client.py` | Direct jXchange requests, built and read through the generated models |
| `silverlake_demo/mock.py` | Six simulated jXchange operations and fictional data; validation of every SOAP body |
| `silverlake_demo/contract.py` | Archive checks, safe extraction, WSDL SOAPActions, and schema loading |
| `silverlake_demo/vendor_models/`, `make_models.py` | Python dataclasses generated with xsdata from the two pinned jXchange schemas (names, types, required fields; no vendor descriptions), kept to what the six operations' requests and replies reach. For `AcctInq`, only the loan payment record the client reads (`LnAcctInqRec` / `x_LnInfoRec` / `LnInfoRec`) is generated, not the whole `AcctInqResponse`, which alone would be about 49,000 lines |
| `silverlake_demo/vendor_api.py` | Which model belongs to each request and reply, XML reading and writing through them, and a strict Pydantic `TypeAdapter` check of every model |
| `silverlake_demo/recorded_exchanges.py` | The example's own recorded SOAP bodies (fictional data), used by the model round-trip tests |

### Supported banking operations

The mock implements six jXchange operations. These names belong to the banking API; they are not necessarily the names of the seven MCP tools.

| Operation | Purpose in this example |
|---|---|
| `AcctSrch` | Find accounts |
| `AcctBalInq` | Read an account balance |
| `AcctHistSrch` | Read recent account transactions |
| `AcctInq` | Read loan information |
| `LnPayoffInq` | Read a supplied payoff quote for a date |
| `XferAdd` | Request an immediate internal transfer |

Automated clearing house (ACH) transfers and future-dated transfers are refused. ACH is a separate bank-payment network; this demo only supports the immediate internal-transfer case.

### Files that stay out of Git

No Jack Henry archive or extracted schema is included in this repository. You download the vendor definitions yourself using `make download`.

- `vendor-inputs/` holds downloaded vendor input and is ignored by Git.
- `var/` holds runtime data and is ignored by Git.
- `var/private/journal/` holds the transfer journal. It records a caller, an opaque operation ID, and a state—never an amount, account, or transcript.

The archive is **pinned**: the example records the exact version it was tested with and its hash, a fingerprint of its contents (see [VENDOR-FILES.md](VENDOR-FILES.md)). A different archive starts the example only if every request it sends and every reply it reads still fit the schemas; otherwise startup stops and names the operation.

### Run the checks

These commands are for developers inspecting or changing the example. Run them from this example's folder in a terminal that is not occupied by the running server.

```bash
make test
```

Runs source, host, journal, and SOAP mock tests. **Schema tests skip if the archive is missing.** Run `make download` first if you want those tests included, and inspect the results for skipped tests.

The models in `silverlake_demo/vendor_models/` are generated, never edited by hand. To regenerate them (needs the pinned archive in `vendor-inputs/`), run `make models`; `make models-check` fails if the committed models differ from a fresh generation. The example needs one new runtime dependency, `xsdata==26.10` (without its `[cli]` extra): the client builds every request and reads every reply through these dataclasses with xsdata's XML parser and serializer, and the generated classes use its date type. The generator itself (`xsdata[cli]`) and its ruff formatter are in the development-only `models` group and are installed only for these two commands. Money and rates are `Decimal` throughout; no amount passes through a float. The models keep everything the six operations' requests and replies reach, with one exception: for `AcctInq`, only the loan payment record the client reads is generated, not the whole `AcctInqResponse`. The schema validation of every SOAP body stays as before; the models add typed access on top of it.

```bash
make validate
```

Validates the Rasa project configuration. This is separate from testing a conversation.

```bash
uv run --locked python tests/live_text_check.py
```

Runs a live text check through the REST channel with a real model. REST is the hypertext transfer protocol (HTTP) text interface used by the test, rather than the microphone. `uv run --locked` uses the project's locked dependency versions.

This live check needs all three configured secrets and the downloaded archive. It consumes API usage and is not included in `make test`. Passing it does not verify speech recognition, spoken replies, or voice latency.
