# Jack Henry SilverLake banking demo (voice)

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-jack-henry-silverlake/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, configured by the operator as repository or organisation Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Talk to a fictional bank by voice. The assistant lists accounts, reads a balance, reads recent transactions, tells you the current payment due and the next due date of a loan, gives a dated loan payoff when one is supplied, and moves money between your own checking and savings accounts after you say `confirm transfer`.

Behind it sits a local **mock of Jack Henry SilverLake**, speaking jXchange SOAP. You download Jack Henry's own published schema archive yourself; this example checks the file and validates every request and every reply against it. Nothing here contacts Jack Henry, and no Jack Henry account is needed.

**What this proves and what it does not.** The mock proves our conversation design and our code against the shapes Jack Henry publishes. It does **not** prove that this works with a real SilverLake system, which needs a bank, an agreement and credentials this example does not have. Every person, account and amount is invented.

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, text conversation only (development build)
Assessed by:   Source tests with the real schemas, and a live text check in a Codespace
Verified with: The pinned jXchange archive, schema validation of every SOAP body, a real model over the REST text channel; spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
```

## Before you start

You need two things, and both are free to set up.

1. **A GitHub account.** Sign in at <https://github.com>.
2. **Three Codespaces secrets**: `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`. Add each at <https://github.com/settings/codespaces> under **Secrets**: click **New secret**, type the name exactly, paste the value, and under **Repository access** choose this repository. Never type these into a file or a chat.

## Walkthrough

Follow the steps in order. Take your time: the first start-up has a long wait.

> Each step says what to click and what you should see. If your screen does not match a step, stop and ask the maintainers before going on.

### 1. Open the example in a Codespace

1. Click the badge at the top of this page that shows the GitHub Codespaces logo with the word “Open” on it.
2. A page titled **Create codespace** opens. Click the green **Create codespace** button.
3. Wait. A browser tab shows a code editor while it builds; this takes a few minutes. You are ready when the black panel at the bottom (the **terminal**) ends with the word `READY`.

### 2. Put Jack Henry's file in the example

1. Click once inside the terminal at the bottom of the window. It is already in the right folder.
2. Type this one line and press Enter. It downloads Jack Henry's public schema archive into a folder named `vendor-inputs`:

   `make download`

3. The terminal prints `Saved and checked`. If it prints anything else, the file is not the expected one; do not continue.

### 3. Start it

1. In the same terminal, type `make run` and press Enter.
2. The first start takes a little longer while the schemas load. The terminal prints `Vendor definitions: found and hash-verified` and a line starting `Open the Inspector:` followed by a long link.

If it prints `Not ready.` instead, it says what is missing in plain words: usually the file is not in `vendor-inputs`, or one of the three secrets is not set for this repository.

### 4. Open the Inspector

1. Hold Ctrl (Command on a Mac) and click the long link in the terminal.
2. If the link does not open, click the **Ports** tab next to the terminal, find port `5005`, and click the small globe icon on its row.
3. A page called **Inspector** opens in a new browser tab.

### 5. Allow the microphone

1. Your browser asks to use the microphone. Click **Allow**.
2. Use only fictional things. Do not say a real name, account or card number: the speech provider receives your audio.

### 6. Talk to the bank

The assistant already knows one fictional customer. Say each sentence and wait for the reply. Numbers below are the invented data in the mock.

| Say | You should hear |
|---|---|
| "What accounts do I have?" | `checking-A`, `savings-A` and `loan-A` |
| "What is my checking balance?" | USD 1,250.00 available |
| "What did I spend recently?" | Up to three recent transactions, said to be the ones returned |
| "What is my next loan payment?" | Two separate facts: current payment due USD 242.40; next due date December 1, 2026 |
| "What is my loan payoff on November 20, 2026?" | USD 4,120.55 for that date |
| "What is my loan payoff on December 24, 2026?" | A plain no: no quote is supplied for that date. It does not calculate one |
| "Verify me." | That your verification was refreshed. Do this just before a transfer; it lasts about a minute |
| "Move 25 dollars from checking to savings." | The exact transfer read back to you, and an instruction to say `confirm transfer` next |
| "Confirm transfer." | `accepted`, and a reminder that accepted is not the same as posted |

Things to try on purpose:

- After a review, say something else instead of `confirm transfer`. The review is cancelled and nothing moves.
- Ask for another person's account, for example `checking-B`. It refuses.
- If a transfer is refused because verification is stale, say `verify me` and ask again.

If it takes more than a couple of seconds to answer, note how long and tell the maintainers: response time is still being measured.

### 7. Stop it

Click inside the terminal and press **Ctrl+C**. The terminal returns to a prompt and the Inspector tab stops working.

### 8. Delete the Codespace

A Codespace you stop but do not delete keeps using your storage.

1. Open <https://github.com/codespaces>.
2. Find this Codespace, click the three dots on its row, then **Delete**.

## What is inside

| File or folder | What it does |
|---|---|
| `silverlake_demo/contract.py` | Checks the downloaded archive, extracts it safely, reads SOAPActions from the WSDLs and loads the schemas |
| `silverlake_demo/mock.py` | The local SOAP mock: six jXchange operations, fictional data, every body validated |
| `silverlake_demo/client.py` | Our direct jXchange client |
| `silverlake_demo/server.py` | The MCP server the assistant calls: exactly seven tools |
| `silverlake_demo/service.py` | Ties the host policy and journal to the client |
| `host.py`, `journal.py` | The host review policy (assurance, review, next-turn confirmation) and the durable transfer journal |
| `skills/banking/` | The assistant's skill and its tool bindings |

The six jXchange operations are AcctSrch, AcctBalInq, AcctHistSrch, AcctInq (loan), LnPayoffInq and XferAdd (immediate internal transfer only; ACH and future-dated modes are refused). The assistant also has one Rasa-side trigger, `banking_submit_transfer`. It is not an MCP tool and carries no authority: the host sends only after it has seen your next raw turn say `confirm transfer`.

### What stays out of this repository

No Jack Henry file is stored here: no archive, no extracted schema and no copy. `vendor-inputs/` and `var/` are ignored by Git. If the file is not exactly the one this example was written for, it refuses to start rather than guess.

### Honest limits

- **Wire shape, not behaviour.** Schema-valid replies say nothing about how a real SilverLake system answers, or which fields it supports for a given loan type.
- **The archive's XML-signature schema is not loaded.** It declares a DTD entity, which this example refuses to process; that optional security namespace stays unresolved. None of the six operations here needs it.
- **Business errors** come back as SOAP faults (for example zero amount, `100199`); the client treats any fault as a refusal and never overrides it.
- **Identity is simulated.** One fixed fictional caller. This is not bank sign-in.
- **Accepted is not posted.** `RsStat` Success means the request was taken.
- **Unknown stays unknown.** If a transfer reply is lost, the example never resends. The journal holds new transfers for that caller across restarts.
- **Not done yet:** a recorded spoken run, response-time measurement, and an audited reset command for the journal.

## For developers

```bash
make test           # source, host, journal and SOAP mock tests; schema tests skip without the archive
make validate       # Rasa project validation
```

A live text check goes through the REST channel with a real model (a few cents, needs the three secrets and the archive). It is not part of `make test`:

```bash
uv run --locked python tests/live_text_check.py
```

The journal lives in `var/private/journal/` (ignored by Git). It records a caller, an opaque operation id and a state; never an amount, an account or a transcript.
