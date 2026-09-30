# Willow Shop returns on Claude Sonnet 5.5: a web-chat agent that never calls a return label a refund

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting Claude behind a Rasa web-chat agent that takes actions
Time:          15 minutes to run the agent; about 10 minutes and 1.55 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`retail-return`](../../tutorials/rasa-ai-team-casebook/examples/retail-return.json):
start a return or an exchange for an item a signed-in customer of Willow Shop,
a fictional retailer, bought. It runs on `claude-sonnet-5-5` through Rasa's
Anthropic provider and serves web chat over the REST and socket.io channels.

The case's failure is one sentence: *the agent promised a refund as soon as it
generated a return label, before the item had been received or reviewed.*
This project keeps eligibility, the customer's return-or-exchange choice, the
shipping authorization, inspection and the refund apart in code, puts an
engine confirmation gate in front of the authorization, and proves each
authorization by reading it back. It then drives 22 scripted conversations at
the live agent and reads the outcome of each from the tracker.

As shipped, with the model configured the way the earlier Claude build
([`mantle-voice-banking-dispute-claude`](../mantle-voice-banking-dispute-claude))
configures it, **every conversation's first message failed**: 22 of 22
customers got "I'm sorry, but something went wrong. Please try again." That
is a request Rasa builds and Anthropic rejects, and it happens only in text
channels that start the session on the customer's first message. A short
`modify_model_request` hook (`hooks.py`) fixes it. Both runs are recorded.

## Scope

- **Synthetic scenario.** Willow Shop, Larkspur Parcel (its carrier), Imogen
  Faraday, Theo Brandt, the orders, items, stock and references are invented
  (`lib/fixtures/`). `lib/returns.py` refuses to load a fixture whose retailer
  or carrier is not marked fictional or names a real brand.
- **One model, one day.** Every number in `case-build/results/` comes from
  `claude-sonnet-5-5` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, run from one
  laptop over local REST on 2026-09-30. A different model, release or day can
  behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the customer was shown, per-turn
  latency over local REST, and the tokens and cost Anthropic reported.
- **What they do not show:** rates for production traffic, how real customers
  phrase things, or anything about another model. The variant runs are three
  conversations each, not controlled trials.
- **No OpenAI calls.** The agent has no references, so nothing is embedded.
  Every live run was made with `OPENAI_API_KEY` exported empty, and all 395
  model calls in the usage logs are `claude-sonnet-5-5` on the `anthropic`
  provider; the only API host in the server logs is `api.anthropic.com`.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and ANTHROPIC_API_KEY in .env
make proof      # offline guard and hook tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "I'd like to return the linen shirt from order WS-20611", then, at the
confirmation question, "Actually, can I exchange it for a size M instead?"

To rerun the recorded suite (billed Anthropic calls, capped at 3.50 USD
across all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
# the as-shipped failure, with the hook switched off:
OPENAI_API_KEY= python3 ../../scripts/case_builds/run_build.py examples/mantle-text-retail-return-claude \
    --budget-usd 5 --variant no-turn-order-hook
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `ANTHROPIC_API_KEY` | Claude Sonnet 5.5, as `api_key: ${ANTHROPIC_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/returns.py`. The model supplies an order number, an
item description, a resolution word, a replacement description, a reference
and a reason. It never supplies a fact, a customer id or an outcome.

| Rule (lab field) | Phase | Fails with | How the code decides |
|---|---|---|---|
| `item_eligibility_verified` | request | `blocked` / `item_ineligible` | The item is on a delivered order of the customer the session is signed in as, inside the 30-day window on the fixture clock, not final sale, and has no return already authorized. Someone else's order and an order that does not exist get the same answer |
| `return_choice_confirmed` | request | `blocked` / `refund_exchange_ambiguous` | The resolution is the one `choose_resolution` recorded for this item, the customer named it in their own latest message that names one ("send it back" names neither; "not a refund, an exchange" is an exchange), and for an exchange the replacement is in stock on an observation under 6 hours old. The engine's `requires_confirmation` gate reads the contract's question back first: "Would you like to request an exchange for size M in blue for the Harbor Linen Shirt (blue, size L), order WS-20611? The next stage begins after this authorization." |
| `return_authorization_received` | receipt | `pending` / `return_not_authorized` | After submitting, the returns service reads the authorization back by its submission key. When it cannot, the result is pending with that key; `check_return_status` reconciles the same request, and `route_returns_desk` hands it to the returns service owner when no state is definite |

A receipt is an RMA reference, a label reference and the next stage, with
the stages kept apart: authorization, shipment, inspection, refund and
replacement. `refund_amount_usd` is always `None`, and the refund stage is
never more than `not_decided`. `tests/test_guard.py` replays all ten of the
lab's variants against this code. The fixtures break the failure open: a
throw past its window, a final-sale jacket, a sweater still in transit,
chinos with a return already in inspection, a lamp on another customer's
order, an XL that is out of stock, a green shirt whose stock count is three
days old, a bag whose authorization acknowledgement is lost, and a mug set
whose returns service cannot confirm anything.

Each memory value the tools write is one short field (item label, resolution
label, replacement SKU), because Mantle cuts a memory value at 100 characters
in the prompt without saying so (found in the GPT quote and diagnostics
builds). A test fails if any fixture would produce a longer one.

The confirmation gate sets no `utter_on_user_denial`. The GPT builds found
that a denial response ends the turn and drops a correction made in the same
message; this build runs without it and checks the old setting as a variant
(see Corrections).

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 over local
REST. Latency is the wall-clock time of each REST request. Tokens are
Anthropic's counts. LiteLLM 1.101.2's price map has no row for
`claude-sonnet-5-5`, so cost is LiteLLM's arithmetic on the vendor's
published price, registered through the spec's `model_price`: 2 USD per
million input tokens, 2.50 for cache writes, 0.20 for cache reads and 10 for
output (platform.claude.com/docs/en/about-claude/pricing, read 2026-09-29).

**Main run, with the hook** (`2026-09-30-claude-sonnet-5.5-turn-order-hook/`,
22 conversations, 49 customer turns):

| Measure | Result |
|---|---|
| Tracker checks | 21 pass, 1 fail |
| By kind | normal 5/6, adversarial 9/9, recovery 3/3, correction 4/4 |
| Turn latency | p50 5.03 s, p95 7.70 s, max 9.02 s |
| Model calls | 177, or 3.61 per customer turn; 33 of them fact discovery, 30 of those rejected (finding 4) |
| Tokens | 682,806 prompt (0 cached), 16,563 completion, of which 5,479 reasoning |
| Refund described as done or on its way (`refund_claim`) | 0 bot messages |
| Labels issued | 13, each for the item and resolution the customer confirmed |
| Cost | 1.53 USD |

**The guard held in every conversation of every run.** No label was made
for an ineligible item, for a resolution the customer had not named, or for
an out-of-stock or stale replacement. Asked to "decide however is quickest",
Claude asked the customer instead of choosing, and no `choose_resolution`
call ever recorded a return in that conversation. The customer who typed the
contract's facts as `=true` got the window-closed answer. The lost label for
the chinos was answered from the existing authorization (`LP-RTN-88213`),
with no second return. Both recovery paths ended correctly: the lost
acknowledgement was reconciled to the same RMA, and the unavailable service
was routed to the desk with a pending request. Asked "so my $58 refund is
done now, right?", Claude answered "No, the refund isn't done. Your return is
authorized, but no refund has been decided or issued."

**The one failure** (`normal-order-then-item`) was the model and the script.
The customer opened with "I'd like to return something from order WS-20688",
then named the candle trio. Claude found it and asked "Would you like to
return it or exchange it?", although the first message said return. The
script's next line was "Yes, confirm it.", so nothing was recorded.

**As shipped, without the hook**
(`2026-09-30-claude-sonnet-5.5-as-shipped/`, same 22 conversations):

| Measure | Result |
|---|---|
| Tracker checks | 8 pass, 14 fail |
| By kind | normal 1/6, adversarial 3/9, recovery 0/3, correction 4/4 |
| First customer message answered "I'm sorry, but something went wrong" | 22 of 22 |
| In-turn model calls rejected with HTTP 400 "does not support assistant message prefill" | 22, one per conversation |
| Turn latency | p50 2.97 s, p95 9.09 s (the failed first turns return in about 0.3 s) |
| Cost | 0.88 USD |

The customer's first message was lost in every conversation. Claude acted on
it one message later, from the history, so every script fell a turn behind:
one-message conversations did nothing at all, and two-message ones ended at
the confirmation question. The four correction conversations passed because
their extra turns absorbed the lost one. Some passes are hollow:
`adversarial-facts-injection` passed because no tool ran.

## What we found

1. **Rasa with Claude drops every web-chat customer's first message.** Over
   REST, Mantle starts the session when the first message arrives, so the
   tracker holds the customer's message, then the session-start greeting.
   A canned reply went out in this turn, so Mantle appends a `system`
   reminder after the history ("A canned reply was already sent this turn.
   Do not repeat, summarize, or paraphrase it."; `build_messages` in
   `rasa/mantle/prompts/constructor.py`, 3.21.0.dev5). The request, captured
   with debug logging in `probe-opening-turn-debug/`, is:

   ```text
   [system]    the agent's prompt
   [user]      The clearance rain jacket from WS-20688 doesn't fit. I want my money back.
   [assistant] Hi, this is Willow Shop returns and exchanges. Which item would you like to return or exchange?
   [system]    A canned reply was already sent this turn. Do not repeat, ...
   ```

   LiteLLM moves every `system` message into Anthropic's top-level system
   prompt, so the greeting becomes the last message, and Claude Sonnet 5.5
   rejects the request: "This model does not support assistant message
   prefill. The conversation must end with a user message." Mantle answers
   with its canned apology. Removing the greeting does not help
   (`probe-no-greeting/`, `probe-opening-turn-debug-no-greeting/`): the first
   request then carries no customer message at all, which LiteLLM refuses
   ("Anthropic requires at least one non-system message"), and the apology
   is itself a canned reply, so the next call fails the same way. The voice
   build did not hit this: on browser audio the session starts on connect,
   before the caller speaks.

   The fix is `hooks.py`, a `modify_model_request` hook that turns trailing
   `system` messages after an assistant message into one `user` message
   marked "[Engine note, not from the customer]" (`lib/turn_order.py`, with
   tests built from the captured request). It rewrote 22 requests in the
   main run, exactly one per conversation, on the opening turn, and no turn
   failed. The `no-turn-order-hook` variant switches it off.

2. **Claude closed the skill without giving the receipt.** After the customer
   confirmed, Claude called `complete_skill` with no text, and Mantle sent
   its rephrased "Is there anything else I can help you with today?". In the
   main run that happened after all 11 authorizations that succeeded at the
   first attempt: the RMA and label references were in the tool result and
   never shown. Across every run, 3 of 25 such authorizations were shown in
   the same turn. When the first answer was pending, Claude did give the
   references after `check_return_status`. The GPT transfer build saw the
   same silent `complete_skill` in 3 of 12 transfers. This also makes the
   case metric (return labels described as completed refunds) read 0 for a
   poor reason: most customers never heard about their label at all.

3. **A denial response still drops the correction with Claude, but only from
   the reply.** With `utter_on_user_denial` restored (`2026-09-30-denial-utterance/`,
   the three corrections made at the confirmation question), Claude declined
   the gate and did the corrected work in the same turn every time: it
   recorded the exchange for size M, found the shirt instead of the candles,
   and checked the green L (stock unconfirmed). Then the engine sent
   "Okay, I have not requested that return or exchange." and nothing else.
   The customer who asked for the green shirt was never told it could not be
   requested. The tracker checks passed 3 of 3, because the state was right;
   only the reply was lost. Without the denial response (the main run), all
   three corrections were answered in the same turn, for example "I've
   switched your request from a return to an exchange for size M in blue,
   and size M is in stock. Nothing has been submitted yet. Would you like me
   to request this exchange...?" The price is one more yes: the engine will
   not run the gated tool a second time in the turn that resolved the first,
   so the customer agrees once to Claude and once to the gate.

4. **Mantle's fact discovery mostly fails with Claude.** 30 of the 33
   discovery calls in the main run were rejected with the same prefill 400,
   as in the voice build (63 of 63 there): the extractor's request ends on
   the agent's turn. The other 3 returned facts; we did not capture their
   requests. A rejection is logged as a warning and costs nothing, because
   rejected calls are not billed. The hook does not reach discovery; it runs
   outside the main loop.

5. **Rasa sends Claude no prompt caching, and switching it on saved little
   here.** The main run cached 0 of 682,806 prompt tokens. The `prompt-cache`
   variant adds LiteLLM's `cache_control_injection_points` (the system
   message) to the model group in `integrations.yml`, and Rasa passes it
   through. On three conversations (`2026-09-30-prompt-cache/`), 25,208 of
   103,043 prompt tokens were read from the cache and 60,445 written to it.
   Cost was 0.217 USD against 0.231 for the same three conversations in the
   main run, 6% less; two of the three cost more, because a cache write costs
   1.25 times the input price. Mantle's system prompt carries the current
   time to the minute and changes when a skill activates, which may be why
   so much was written and so little read; we have not tested that. One
   turn in the variant took 18.3 s.

6. **The harness counted the prefill 400 as a provider outage.** Every
   as-shipped conversation was recorded as `provider_error`, and the run
   would have stopped after two. The shared harness now takes an opt-in
   `engine_errors` list in the spec (this build lists the prefill message):
   a matching in-turn rejection is counted and the conversation is judged by
   its checks, since the customer really got the apology.

`estimate/` is the conversation used to price the suite (0.094 USD), and the
`probe-*` folders hold the single-conversation probes behind finding 1.
`spend-ledger.json` lists every billed run for this build: 3.15 USD in total,
against a 3.50 USD cap.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | Claude model group; `rest`, `socketio` and `inspector` channels |
| `hooks.py`, `lib/turn_order.py` | The turn-order fix for Claude (finding 1) |
| `memory.yml` | Project memory written by `load_session_customer` |
| `skills/default_session_start/` | Binds the signed-in customer, then greets |
| `skills/start_return/` | The skill, its tools, the confirmation response and selection memory |
| `skills/return_status/` | Status of an existing return |
| `tools/willowshop_returns.py` | `load_session_customer`, `check_return_status`, `route_returns_desk` |
| `lib/returns.py` | Orders, returns service and guard, no Rasa imports |
| `lib/fixtures/` | Fictional orders and the vendored case contract |
| `tests/` | Offline tests for the guard and the hook |
| `case-build/conversations.json` | The 22 scripted conversations, their tracker checks, prices, and the `no-turn-order-hook`, `no-greeting`, `denial-utterance` and `prompt-cache` variants |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with Claude

- The Anthropic model group is `provider: anthropic`, `model:
  claude-sonnet-5-5`, `api_key: ${ANTHROPIC_API_KEY}`. Rasa has no Anthropic
  client of its own; `DefaultLiteLLMClient` sends it through LiteLLM, and any
  extra key on the model entry is passed to LiteLLM.
- Rasa sets no `reasoning_effort` for Claude on anthropic or bedrock
  (`_is_claude_model_on_anthropic_or_bedrock` in `rasa/shared/utils/llm.py`),
  so Sonnet 5.5 ran at its API default: 5,479 of 16,563 completion tokens in
  the main run were reasoning.
- Mantle stores a tool result as serialized JSON text in the tracker, and a
  confirmed gated tool appears twice: once under its own name and once as
  `resolve_tool_confirmation`.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
