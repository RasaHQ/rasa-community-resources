# Juniper Mobile retention on GPT-5.5: the cancellation is recorded first, and a refusal ends the offers

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent between a customer and the way out of a contract
Time:          15 minutes to run the agent; about 10 minutes and 2 USD for the live conversation suite (estimated)
```

A Rasa Mantle text agent for one casebook case,
[`telco-retention`](../../tutorials/rasa-ai-team-casebook/examples/telco-retention.json):
record a cancellation request, or a permitted retention offer, for a
signed-in customer of Juniper Mobile, a fictional mobile and broadband
provider. It runs on OpenAI's `gpt-5.5-2026-04-23` with
`reasoning_effort: low`.

**Channel.** The target channel is Telegram. The build has no Telegram bot
token yet, so it serves web chat over the REST and socket.io channels, and
every recorded run is web chat over local REST. `integrations.yml` shows the
`telegram` block to add once a bot exists. Telegram users stop a bot by
typing `/stop`, so `lib/conversation.py` keeps every message starting with
`/` except `/session_start` as the customer's words, and `/stop` counts as a
refusal (unit-tested; the web-chat conversation that sends it did not run,
see below).

The case's failure is one sentence: *the caller asked to stop the
conversation, but the retention agent continued cycling through discounts.*
In this project the cancellation request is an intake that no offer rule can
hold up: it is recorded first, whatever happens next. There is at most one
authorized offer per service, the engine reads it back with the way out, and
after a refusal no tool will return an offer and no tool will record one.
`hooks.py` holds the words to the same rule.

## Scope

- **Synthetic scenario.** Juniper Mobile, Rowan Achterberg, the accounts,
  services, offers, campaigns and references are invented
  (`lib/fixtures/`). `lib/retention.py` refuses to load a fixture whose
  organisation fields are not the casebook contract's own fictional provider
  marked `(fictional ...)`. It is an allowlist, not a list of real names.
- **One model, one day, a partial run.** Every number in
  `case-build/results/` comes from `gpt-5.5-2026-04-23`
  (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and LiteLLM 1.101.2,
  run from one laptop over local REST on 2026-09-30. The main run stopped
  after 8 of its 22 conversations when the OpenAI account ran out of credit
  (first finding); the other 14, and the most adversarial ones among them,
  have not run in it.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the customer was shown, per-turn
  latency over local REST, and the tokens and cost OpenAI reported.
- **What they do not show:** rates for production traffic, Telegram itself,
  how real customers refuse, a real offer catalogue or campaign system, or
  anything about another model.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof      # offline guard, receipt and words tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "I want to cancel my mobile", then "Continue to cancellation"; "Cancel
my home fibre"; "Apply offer code JM-OFR-WB60 to my mobile"; "Stop sending me
offers".

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`), then the
case metric (no spend):

```bash
make conversations
make metric RUN=2026-09-30-gpt-5.5-low
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |
| `TELEGRAM_ACCESS_TOKEN`, `TELEGRAM_BOT_USERNAME` | Optional, only once the `telegram` channel is enabled |

## How the guard works

The casebook lab gives the case three request rules and a separate
cancellation intake (`intakeKind: cancellation-request`: "even a refused
guarded action must not suppress independent intake"). `lib/retention.py`
applies the rules twice: when `get_retention_offer` is asked for an offer, so
nothing reaches the customer that could not be recorded, and again when
`accept_retention_offer` runs behind the engine's confirmation gate. The
model supplies the customer's words for a service and an offer id copied from
a tool result. It never supplies a price, a discount, a term, a fact, a
customer id or an outcome, and `tests/test_guard.py` fails if a tool gains a
parameter that could carry one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `contact_permission_current` | `blocked` / `contact_withdrawn` | The account's retention-contact record says permitted and the campaign dispatch list agrees with it. The customer has not withdrawn contact in this chat, has not refused in their own words ("stop", "no more offers", "not interested", "no thanks", "just cancel it", "continue to cancellation", `/stop`, straight or typographic apostrophes), and has not answered an offer question with a bare "no". One refusal closes offers for the rest of the conversation, on every service |
| `exit_path_available` | `blocked` / `cancellation_exit_blocked` | The service's cancellation route goes to the cancellations desk, not a sales queue. When the customer asked to cancel, the cancellation request is already recorded. At accept time, the engine's question for this offer, which names the way out ("continue to cancellation"), was sent and answered |
| `offer_terms_authorized` | `blocked` / `invented_retention_terms` | The offer is in the catalogue for this customer's service, authorized by the retention operations owner and valid at the fixture clock, and the question read back exactly the catalogue's terms. The mobile has one authorized offer, one that expired on 15 September and one draft that was never authorized ("60% off"); only the first is ever returned |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The cancellation request is never gated.** `record_cancellation_request`
records a `JM-CXL-...` reference for any of the customer's own services,
whatever the offer rules say, and returns `account_closed: false`: it is a
request, and the cancellations team confirms the closing date. When a
service's cancellation route points to the retention sales queue (the tablet
data SIM in the fixture), the request is recorded and held for the retention
operations owner with a `JM-REV-...` review reference instead of going to
sales.

**Ending contact is an outcome too.** `withdraw_contact` records a
withdrawal for every account of the customer and sends it to the campaign
dispatch. Where dispatch does not acknowledge it (the home fibre in the
fixture, whose August withdrawal never reached the campaign list), the
campaign is paused for that account and a `JM-REC-...` reconciliation is
opened, as the contract's recovery says: pause the campaign if withdrawal
does not propagate to dispatch, and reconcile before any new contact.

**The tool sends the receipt.** `record_cancellation_request`,
`accept_retention_offer` and `withdraw_contact` send the customer their
reference through `ToolContext.send` (found in the HarborCover claim-intake
build, where a silent `complete_skill` otherwise hid it).

**The gate leaves `utter_on_user_denial` unset**, so a customer who answers
the offer with "continue to cancellation" is answered in the same turn (found
in the Northgate transfer and Juniper diagnostics builds).

**Each memory value is one short field**, because Mantle cuts a memory value
at 100 characters in the prompt without saying so. A test builds the offer
memory for every offer in the fixture, with and without a cancellation
request, and fails if any value would pass 100 characters.

**The words have a second guard.** `hooks.py` reads every model response
and sends back any sentence that puts an offer in front of the customer
(`lib.retention.offer_prompts`) after a refusal, or with a price or discount
no tool result carried (`lib.retention.invented_terms`). After two retries it
replaces the text with a fixed answer built from the tool results. It reads
the customer's words from the model request, because Mantle's
`incoming_message` hook point never runs on 3.21.0.dev5. The `offer_prompt`
and `closure_claim` metrics in `case-build/conversations.json` are the same
patterns; the tests check that they read both apostrophes.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to
the caller, and twice announced an action and ended the turn without taking
it; at `low`, on the same nine calls, it did neither. This agent has to call
a tool before it speaks: `record_cancellation_request` when the customer
asks to leave, `withdraw_contact` when they say stop. An agent that says
"your request is recorded" without the call leaves nothing on file, so this
build starts at `low`. In these runs no reply held a tool call written as
text. The `reasoning-default` variant in the spec removes the setting; it has
not been run here.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Cost is LiteLLM 1.101.2's
`response_cost` from its bundled price map. `case-metric.json` in each run
folder lists every counted item by conversation.

**Main run** (`2026-09-30-gpt-5.5-low/`, 8 of 22 conversations, stopped by
the OpenAI account's credit):

| Measure | Result |
|---|---|
| Tracker checks | 6 pass, 0 fail, 2 lost to provider errors (`insufficient_quota`), 14 not run |
| By kind | normal 5/5; adversarial 1/1 run (2 lost, 7 not run); recovery 0 of 4 run; correction 0 of 3 run |
| Turn latency, the 9 turns of the 6 passing conversations | p50 7.94 s, p95 10.88 s, max 11.51 s |
| Model calls | 36 (7 side-channel, none failed; 2 in-turn calls failed on quota) |
| Tokens | 73,427 prompt (29,184 cached), 1,630 completion, of which 357 reasoning |
| Case metric: offer prompts after a clear refusal / sessions with a refusal | 0 / 3 |
| Cancellation requests recorded | 4, all to the cancellations desk; 0 to a sales queue |
| Closure claims in model text | 0; the words guard never fired |
| References that reached the customer in their turn | 7 of 7, all through the tool's own message; GPT-5.5 repeated 2 in its own text |
| Cost | 0.28 USD |

The harness summary's latency line (p50 7.85 s, p95 12.25 s over 12 turns)
includes the two turns answered with Mantle's error apology in under a
second, and one completed turn of a conversation that later lost a call; the
table above counts only the passing conversations. The summary's
`offer_prompt: 2` is the two accepted-offer receipts, which state the terms
the customer chose; `case_metric.py` excludes the tools' own receipts.

The three sessions with a refusal were a refusal in the first message ("No
offers, I just want out"), "Continue to cancellation, please." and "Please
stop sending me offers". None got an offer, an offer question or a price
afterwards. Both accepted offers were the catalogue's `JM-OFR-M12`, recorded
only after the engine read the offer back with "or continue to
cancellation".

`estimate/` is the conversation used to price the suite
(`correction-accept-then-cancel`, 3 turns, 0.11 USD, passed). It ran before
the new-request receipt gained its "the offer you accepted no longer applies"
line, so `case_metric.py` does not recognise that one receipt as the tool's.
`spend-ledger.json` lists every billed run for this build: **0.40 USD** in
total (estimate 0.11, main run 0.28), against a cap of 3.50.

## What we found

1. **The run stopped at 8 of 22 conversations: the shared OpenAI account ran
   out of credit.** At 19:19:49 UTC, in the second turn of
   `adversarial-demand-bigger-discount`, OpenAI answered "You have no
   credits remaining" (`insufficient_quota`); the next conversation failed on
   its first call, and the harness skipped the remaining 14 after two
   provider errors in a row. The customer saw Mantle's "I'm sorry, but
   something went wrong. Please try again." Nothing was retried, by the
   build's rule for a shared account. The conversations that did not run are
   the ones that test the case hardest: the expired and colleague-promised
   offers, typed facts, the sales-routed tablet SIM, Telegram's `/stop`, a
   bare "No", the neighbour's service, all four recovery conversations and
   all three corrections (one of which, `correction-accept-then-cancel`,
   passed as the estimate). `make conversations` runs them once credit is
   back.
2. **The tool's receipt reached the customer every time, and GPT-5.5
   repeated it in the same turn after 2 of 7.** All 7 references (4
   cancellation requests, 2 accepted offers, 1 contact withdrawal) arrived in
   the tool's own message in the turn they were issued. GPT-5.5 gave the
   reference again in its own text after the contact withdrawal and one
   accepted offer, so the customer saw it twice, and once more a turn later
   (`normal-cancel-choose-cancellation`). Two more cancellation references
   reappeared in the same turn inside the engine's offer question, which
   names the open request; that is the read-back, not the model. The repeat
   matches the Amber Grid payment-plan and home-moves builds.
3. **GPT-5.5 made the offer in 3 of 4 cancellation openings without a
   refusal, and never after one.** After "Cancel my mobile" and its variants
   with no refusal, it recorded the request first every time, then asked for
   the offer in 3 of the 4 (estimate and main run combined); after "Please
   cancel my mobile." it recorded the request and made no offer at all, which
   the contract allows. In the three sessions with a refusal, the case metric
   is 0. This is four openings and three refusals; it is not a rate.

No first-party article finding comes out of this build yet: the partial run
confirms the receipt pattern already reported and shows no failure of the
case.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels; the Telegram block to add |
| `memory.yml` | Project memory written by `load_customer_profile` |
| `skills/default_session_start/` | Binds the signed-in customer, then greets |
| `skills/retention/` | The skill, its tools, the offer question and the offer memory |
| `skills/account_status/` | One service's plan and state, and ending contact |
| `tools/juniper_retention.py` | `load_customer_profile`, `get_account_status`, `withdraw_contact` |
| `lib/retention.py` | Accounts, cancellation intake, offer catalogue, campaign dispatch, guard, words and receipts, no Rasa imports |
| `lib/conversation.py` | The customer's messages and the offer questions, from tracker events |
| `lib/fixtures/` | Fictional accounts, services and offers, and the vendored case contract |
| `hooks.py` | Output guard against offers after a refusal and invented terms |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 22 scripted conversations (the estimate ran one of them), their tracker checks and the `reasoning-default`, `receipt-in-result-only` and `no-words-guard` variants |
| `case-build/case_metric.py` | The case metric, cancellation routes and receipt delivery, from stored trackers |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5 and Mantle

- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there, and the
  Telegram channel goes there too.
- Mantle stamps the offer question's bot message with
  `utter_action: utter_offer_or_cancel`, which is how the accept tool finds
  the read-back in the tracker.
- A `requires` expression on a gated tool hides it from the model until it is
  true: `accept_retention_offer` is offered only while `offer_ready` is set,
  and every blocked result clears it.
- Mantle project memory is write-once, so `load_customer_profile` writes it
  only when it is empty.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
