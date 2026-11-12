# Fiserv Premier banking demo (voice)

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-fiserv-premier-11.0.0-prm/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Talk to a fictional bank by voice. The assistant lists accounts, reads a balance, reads recent transactions, tells you the next loan payment and the current payoff, and moves money between your own two accounts after you say `confirm transfer`.

Behind it sits a local **mock of Fiserv Banking Hub (Premier)**. You download Fiserv's own API definition files yourself; this example checks the file, builds the mock from it while it starts, and the assistant talks to that mock. Nothing here contacts Fiserv, and no Fiserv key or password is needed.

**What this proves and what it does not.** The mock proves our conversation design and our code against the shape Fiserv publishes. It does **not** prove that this works with a real Fiserv system. Every person, account and amount is invented.

```text
Author:        Rasa Community contributors
Assessed on:   12 November 2026, text conversation only (development build)
Assessed by:   Source tests with the real contract, and a live text check in a Codespace
Verified with: Real OpenAPI validators and loopback mock, the pinned Fiserv ZIP, a real model over the REST text channel; spoken run and latency still open
Installation:  rasa-pro 3.21.0.dev5, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Not yet measured
```

## Before you start

You need three things. Each takes a few minutes and costs nothing to set up.

1. **A free GitHub account.** Sign in at <https://github.com>.
2. **Three Codespaces secrets** with the Rasa licence and the two speech and language keys: `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`. Add each at <https://github.com/settings/codespaces> under **Secrets**: click **New secret**, type the name exactly, paste the value, and under **Repository access** choose this repository. Never type these into a file or a chat.
3. **The Fiserv file** (step 1 below). It is free and public.

## Walkthrough

Follow the steps in order. Take your time: the first start-up has a long wait.

> Each step says what to click and what you should see. If your screen does not match a step, stop and ask the maintainers before going on.

### 1. Download Fiserv's definition file

1. On your own computer, open <https://developer.fiserv.com/product/BankingHub/api> in your browser. If the page asks you to sign in, create a free Fiserv developer account.
2. Click **Download API specifications**.
3. A file named `BankingHub_Premier_api_specs.zip` appears in your Downloads folder. **Do not open or unzip it.**

### 2. Open the example in a Codespace

1. Click the badge at the top of this page that shows the GitHub Codespaces logo with the word “Open” on it.
2. A page titled **Create codespace** opens. Click the green **Create codespace** button.
3. Wait. A browser tab shows a code editor while it builds; this can take several minutes. You are ready when the black panel at the bottom (the **terminal**) ends with the word `READY`.

### 3. Put the Fiserv file in the example

1. In the left panel (the **Explorer**), right-click the folder named `fiserv-premier-11.0.0-prm` and choose **New Folder**. Type `vendor-inputs` and press Enter.
2. Right-click the new `vendor-inputs` folder and choose **Upload…**. Pick `BankingHub_Premier_api_specs.zip` from your Downloads folder.
3. The file now appears inside `vendor-inputs`.

### 4. Start it

1. Click once inside the terminal at the bottom of the window. It is already in the right folder.
2. Type `make run` and press Enter.
3. After a few seconds the terminal prints `Vendor definitions: found and hash-verified` and a line starting `Open the Inspector:` followed by a long link.

If it prints `Not ready.` instead, it says what is missing in plain words: usually the Fiserv file is not in `vendor-inputs`, or one of the three secrets is not set for this repository.

### 5. Open the Inspector

1. Hold Ctrl (Command on a Mac) and click the long link in the terminal.
2. If the link does not open, click the **Ports** tab next to the terminal, find port `5005`, and click the small globe icon on its row.
3. A page called **Inspector** opens in a new browser tab.

### 6. Allow the microphone

1. Your browser asks to use the microphone. Click **Allow**.
2. Use only fictional things. Do not say a real name, account or card number: the speech provider receives your audio.

### 7. Talk to the bank

The assistant already knows one fictional customer. Say each sentence and wait for the reply. Numbers below are the invented data in the mock.

| Say | You should hear |
|---|---|
| "What accounts do I have?" | `checking-A`, `bills-A` and `loan-A` |
| "What is my checking balance?" | USD 1,250.00 available |
| "What did I spend recently?" | Up to three recent posted transactions, said to be the ones returned |
| "What is my next loan payment?" | USD 182.40 due on 1 December 2026 |
| "What is my loan payoff?" | The current payoff, USD 4,120.55 |
| "What is my loan payoff on the 20th of December?" | A plain no: a dated quote is not available. It offers the current payoff instead |
| "Verify me." | That your verification was refreshed. Do this just before a transfer; it lasts about a minute |
| "Move 25 dollars from checking to bills." | The exact transfer read back to you, and an instruction to say `confirm transfer` next |
| "Confirm transfer." | `accepted`, and a reminder that accepted is not the same as posted |

Things to try on purpose:

- After a review, say something else instead of `confirm transfer`. The review is cancelled and nothing moves.
- Ask for another person's account, for example `checking-B`. It refuses.
- If a transfer is refused because verification is stale, say `verify me` and ask again.

The sound is a single synthetic voice. If it takes more than a couple of seconds to answer, note how long and tell the maintainers: response time is something this project is still measuring.

### 8. Stop it

Click inside the terminal and press **Ctrl+C**. The terminal returns to a prompt and the Inspector tab stops working.

### 9. Delete the Codespace

A Codespace you stop but do not delete keeps using your storage.

1. Open <https://github.com/codespaces>.
2. Find this Codespace, click the three dots on its row, then **Delete**.

## What is inside

| File or folder | What it does |
|---|---|
| `premier_demo/contract.py` | Checks the downloaded ZIP and builds request and response checks from Fiserv's own files |
| `premier_demo/mock.py` | The local mock bank: Fiserv's paths and bodies, fictional data |
| `premier_demo/client.py` | Our direct Banking Hub client for five operations |
| `premier_demo/server.py` | The MCP server the assistant calls: exactly seven tools |
| `premier_demo/host.py` | Identity simulator, review, confirmation, one send and a durable journal |
| `skills/banking/` | The assistant's skill and its tool bindings |

The assistant also has one Rasa-side trigger, `banking_submit_transfer`. It is not an MCP tool and carries no authority: it takes no arguments, and the host sends only after it has seen your next raw turn say exactly `confirm transfer`. The MCP server itself offers exactly seven tools.

The five Banking Hub operations are: accounts by party, account (checking) for the available balance, account (loan) for the next payment and current payoff, account transactions, and an immediate own-account funds transfer. The checking and loan operations share one path in Fiserv's files but have different shapes, so they are kept apart by document.

### What stays out of this repository

No Fiserv file is stored here: no ZIP, no extracted definition and no copy of its schemas. `vendor-inputs/` is ignored by Git. If the file you supply is not exactly the one this example was written for, it refuses to start rather than guess. When Fiserv publishes a changed file, a reviewer must pin the new one.

### Honest limits

- **Wire shape, not behaviour.** The mock validates every request and its own replies against Fiserv's published definitions. That does not tell you how a real Premier system answers.
- **Fiserv's error replies cannot be validated.** Their published default reply requires success fields, so an error cannot satisfy it. The mock sends a small status-only error and the client treats any non-success status as unavailable.
- **Savings is not included.** Only checking-type (DDA) and loan accounts are pinned.
- **Dated payoff is not supported.** Only the current payoff is.
- **Identity is simulated.** One fixed fictional caller. This is not bank sign-in.
- **Accepted is not posted.** A valid reply means the request was taken.
- **Unknown stays unknown.** If a transfer reply is lost, the example never resends. It blocks new transfers for that caller across restarts until the fictional exercise is reset (below).
- **Trial sandbox: manual and read-only.** See *Optional: the Fiserv trial* below. The voice assistant always uses the mock.
- **Not done yet:** a recorded spoken run (microphone and speech output), response-time measurement, and a scripted native test without a live model.

## For developers

```bash
make test           # source and mock tests; skips what needs the Fiserv file
make contract-test  # the contract tests (need the Fiserv file; skipped without it)
make validate       # Rasa project validation
```

CI has no Fiserv file, so contract-dependent tests print that they were skipped. A skipped input never qualifies the contract.

A live text check goes through the REST channel with a real model (a few cents, needs the three secrets and the Fiserv file). It is not part of `make test`:

```bash
uv run --locked python tests/live_text_check.py
```

Two optional commands, run in the example folder:

```bash
python run_demo.py --fault transfer-response-lost   # the transfer succeeds but the reply is lost
python -m premier_demo.reset_fixture --reason "starting over" --acknowledge-unresolved
```

The second one only works while the example is stopped. It writes an audit row, keeps the old unknown outcome in history, and starts a new fictional exercise. It never says the old transfer failed or succeeded.

The journal lives in `var/private/` (ignored by Git). It records a caller, an opaque review id, a state and an epoch. It never stores an amount, an account or a transcript.

## Optional: the Fiserv trial (manual, read-only)

If you have a Fiserv Banking Hub trial, you can make a few real read-only calls to the Premier trial environment. This is separate from the voice assistant, which always uses the mock. Nothing here moves money.

What it needs: three Codespaces secrets, `FISERV_BH_API_KEY_NAME`, `FISERV_BH_API_KEY` and `FISERV_BH_API_SECRET`, with this repository selected; and a short budget file you write yourself that says how many trial calls you may use (`var/private/manual-trial-budget.json`; fields are listed in `premier_demo/quota.py`). Without all three secrets and a fresh budget it refuses and the mock stays as it is.

```bash
python -m premier_demo.trial import-budget var/private/manual-trial-budget.json --runner my-codespace
python -m premier_demo.trial read --runner my-codespace --trial my-trial --period 2026-11 --party <party id>
```

How it works: one token per run with HTTP Basic authentication, then at most three core calls, each one counted in a local ledger before it is sent, at least 7 seconds apart. Secrets are read from the environment and never printed. The trial's "no records" answer arrives as a status-only reply that Fiserv's published schema does not allow; the client reports it as "no records match". A trial answer is not production and not certification.

