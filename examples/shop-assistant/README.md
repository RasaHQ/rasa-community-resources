# Shop orders through Telegram and Google Sheets

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/examples-shop-assistant/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `GOOGLE_CLIENT_SECRETS_JSON`, `GOOGLE_TOKEN_JSON`, `SHOP_SHEET_ID`, `SHOP_OPERATOR_CHAT_ID`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **Before the first command:** Create a blank demo Sheet and add the initial Codespace secrets. Google sign-in produces GOOGLE_TOKEN_JSON. All commands run in this Codespace terminal.
- **First command:** `make google-signin`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the Google sign-in link. Paste the final browser address back into this terminal, save GOOGLE_TOKEN_JSON, restart the Codespace, then run make setup-sheet and make run.
<!-- codespaces:end -->

Author: Rasa Community contributors  
Assessed on: 2026-11-15  
Assessed by: Offline shop and consent checks; native processor and MCP protocol checks  
Verified with: rasa-pro 3.21.0.dev5 (synthetic inputs; provider rehearsal has not run)  
Industry: Retail  
You learn: How to review a Telegram basket, record it in Sheets and send a shipping message.  
Catalog name: Telegram shop assistant  
Status: work in progress

This example lets one operator browse products, review a basket and place an
order in a private Telegram chat. Google Sheets holds the catalog and order
rows. Change an order's status to `shipped` in the Sheet to send a shipping
message to the same chat.

**Work in progress:** the direct integration dependency awaits its reviewed
release pin. Provider calls and the complete rehearsal have not run. The
current locks cover the native Rasa, Core MCP and consent checks only.

Rasa reads the shopping request and calls the read or quote tools. Python owns
the prices, confirmation and writes. The model has no order-placement tool.
A separate exact `confirm` reply places the reviewed basket. Any other reply
cancels that review. A changed request can produce a new review.

## Create a blank Sheet

Create a dedicated blank Google Sheet and keep its identifier from the URL.
You do not need to create tabs or paste rows. The setup command creates
missing tabs and seeds empty ones. Use this Sheet only for the example.

## Configure Codespace secrets

Use Python 3.12. Set these values through Codespace secrets, with access to
this repository. Stop and start the Codespace after adding secrets.

| Name | Value |
| --- | --- |
| `RASA_PRO_LICENSE` | Your Rasa license |
| `OPENAI_API_KEY` | Your OpenAI key |
| `TELEGRAM_BOT_TOKEN` | The bot token supplied by BotFather |
| `SHOP_OPERATOR_CHAT_ID` | Your positive private Telegram chat ID |
| `SHOP_SHEET_ID` | The identifier from the dedicated Sheet URL |
| `GOOGLE_CLIENT_SECRETS_JSON` | The complete Google Desktop OAuth client JSON, for consent only |
| `GOOGLE_TOKEN_JSON` | The authorized-user JSON returned by consent; required before setup and run |

Send `/start` to your own bot so it may message you later. It will not answer
until the demo is running. To find your private chat ID, search Telegram for
`userinfobot`, send that bot `/start`, and copy the number after `Id:` into
`SHOP_OPERATOR_CHAT_ID`.

Enable the Google Sheets API for the OAuth client project. If its consent
screen is in Testing, add your Google account as a test user. Use the Sheets
permission; the example needs no Drive-wide permission.

The sign-in command reads client JSON from the environment and keeps the token
in memory. It prints the authorized token for you to save as a Codespace
secret. It does not write client or token files.

## Sign in, set up the Sheet and start

In a fresh checkout, run `make setup` from this example's directory. It creates
three separate environments from their locks: native Rasa, the Core MCP server
and Google consent. It refuses to replace an existing environment. A Codespace
created from this example's launch button performs that setup during creation.

Run every command below in this example's Codespace terminal. First sign in:

```sh
make google-signin
```

Open the printed Google link in your browser and allow Sheets access.
Google redirects to `http://127.0.0.1:8766/`. Your browser should say it cannot
connect; that is expected. Copy the whole address from its address bar and
paste it at the `Address:` prompt in the Codespace terminal. Keep that address
private: it contains a one-time authorization code.

The command checks the redirect and sign-in state, then exchanges the code
using PKCE. It requires a refresh token and prints one token JSON line. Save
that line as `GOOGLE_TOKEN_JSON` in your personal Codespace secrets, grant it
access to this repository, and clear the terminal. Restart or rebuild the
Codespace so its processes receive the new secret.

Then return to this example's Codespace terminal:

```sh
make setup-sheet
make run
```

`make setup-sheet` uses the same Google token and `SHOP_SHEET_ID`. It creates
`Products` and `Orders` only when they are missing. In an empty Products tab,
it writes column names and these initial products:

| Code | Product | PriceCents | Stock |
| --- | --- | ---: | ---: |
| NOTEBOOK | Notebook | 12900 | 12 |
| MARKER | Marker | 4500 | 8 |

Prices use integer MXN cents. Stock is the initial quantity; recorded orders
reduce the available quantity. An empty Orders tab receives these columns:

```text
OrderNumber  QuoteJson  TotalCents  Currency  Status  CreatedUTC  RequestKey
```

Setup reads each whole tab. If it finds any returned row, it leaves that tab
unchanged and tells you. It appends only to empty tabs, using raw values.
It never clears or overwrites cells. Avoid editing the Sheet during setup.
If setup stops with an uncertain result, inspect the Sheet before repeating
it. Do not run two copies of setup or the assistant against the same Sheet.

## Walk through an order

1. Open the bot's private chat and send `/start` if Telegram requires it.
2. Ask, “What products are available?”
3. Ask, “I want two notebooks.” The review should show `MXN 258.00`.
4. Send `confirm` as a new message. Check that one row appears in `Orders`.
5. Ask, “What is my order's status?” It should report `placed`.
6. In the Sheet, change only that row's `Status` cell from `placed` to
   `shipped`. A shipping message should arrive in the same private chat.

Leave the order number, quote JSON, total, currency, date and request key
unchanged. The status edit represents an operator shipping action; it does
not contact a carrier.

A review expires after five minutes. An edited message, photo or unsupported
update cannot confirm it. A confirmation already waiting in the same fetched
batch cannot approve a prompt that the example sends later.

## State and stopping

The example retains incoming updates and send receipts in private SQLite
files under `.state`. It records an order intent before appending to Sheets.
A repeated request key reads the original order; it never appends again.

If a write or Telegram send has an uncertain result, the example stops and
keeps that record. Preserve `.state` and inspect the original result before
restarting. Deleting the journal removes the information needed to prevent
another write. Do not run two copies against the same Sheet.

Ctrl-C requests a clean stop after the current bounded operation. Repeating
Ctrl-C cannot skip closing the owned clients. A run stops after 30 retained
updates or 15 minutes, whichever comes first.

## Development checks

`make test` checks the shop, durable conversation and Google sign-in helper
with synthetic provider responses. `make test-native` uses the actual locked
Rasa runtime and two MCP environments. It checks packaging, processor startup
and the protocol between the native client and Core server. The startup
fixture stubs license validation and blocks network connections.

These checks do not prove Google consent, model behavior or Telegram delivery.
Complete the live walkthrough separately with the configured operator and
dedicated Sheet. This is a teaching shop with a single operator, not a
multi-user inventory system or a payment integration.
