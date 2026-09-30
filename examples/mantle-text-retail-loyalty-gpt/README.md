# Willow Shop subscriptions on GPT-5.5: stop renewal, pause and cancel now as three confirmed commands

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of subscription, membership or loyalty changes
Time:          15 minutes to run the agent; about 10 minutes and 2 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`retail-loyalty`](../../tutorials/rasa-ai-team-casebook/examples/retail-loyalty.json):
change a loyalty or subscription setting for a signed-in member of Willow
Shop, a fictional retailer. It runs on OpenAI's `gpt-5.5-2026-04-23` with
`reasoning_effort: low`.

**Channel.** The target channel is Telegram. The build has no Telegram bot
token yet, so it serves web chat over the REST and socket.io channels, and
every recorded run is web chat over local REST. `integrations.yml` shows the
`telegram` block to add once a bot exists. Rasa's Telegram channel needs
aiogram, which `rasa-pro==3.21.0.dev5` installs only with its `channels`
extra; this project's lock does not include it.

The case's failure is one sentence: *the agent cancelled a subscription
immediately when the member meant to stop its next renewal.* In this project
stopping a renewal, pausing and cancelling now are three separate commands.
The model picks one by name, the engine reads back its effective time and
what the member keeps and loses, and `apply_subscription_change` runs only
the change the member was asked about, at the subscription's current
revision. Then 20 scripted conversations were run against the live agent,
many of them trying to make it do the wrong thing, and each outcome was read
from the tracker. The shared OpenAI account ran out of quota partway through
the first run; a second run completed the other 8, and all 20 pass.

## Scope

- **Synthetic scenario.** Willow Shop, its member Nadia Brennan, her four
  subscriptions, the dates, refunds and points are invented
  (`lib/fixtures/`). `lib/subscriptions.py` refuses to load a fixture whose
  organisation is anything but the casebook contract's own fictional
  retailer.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30. A different model, release, setting or
  day can behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the subscription service returned, what the member was
  told, per-turn latency over local REST, and the tokens and cost the provider
  reported.
- **What they do not show:** Telegram, reliability for production traffic,
  real members' phrasing, a real subscription or billing system, or another
  model. The suite is split over two runs of the same code on the same day,
  not one run. A scripted member cannot answer an unexpected question, so a
  failure can be the script's.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "Cancel my Willow Plus membership", then "Then just stop it renewing",
then "Actually, pause my Coffee Club instead".

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
make metric RUN=<label>   # case metric, words and receipt delivery, no spend
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

For Telegram, add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME` and the
`telegram` block in `integrations.yml`. Neither is needed for web chat.

## How the guard works

The casebook lab gives the case two request rules and one receipt rule.
`apply_subscription_change` enforces them in `lib/subscriptions.py` when it
runs, from the subscription service's state then:

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `change_type_confirmed` | `wrong_subscription_change` | The change type passed is the one selected, and the engine's question for that exact tag (`WS-SUB-3301 stop_renewal r7`) and its plain-words label ("stop the renewal, not an immediate cancellation") is in the conversation's events with a member message after it |
| `entitlement_delta_disclosed` | `benefit_loss_hidden` | The effective time and entitlement line read back are exactly what the service computes for that change at the subscription's current revision |
| `change_receipt_verified` | `change_not_recorded` (pending) | The service's answer names the same subscription and command, with the disclosed effective time and entitlements. A lost answer or a mismatch leaves the change pending |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The question belongs to one change at one revision.** The engine's
question, filled from memory the service wrote: "Please confirm this change
to your Willow Plus membership (WS-SUB-3301): stop the renewal, not an
immediate cancellation. It takes effect 2027-01-12 00:00 UTC. What changes
for you: Plus benefits kept to 2027-01-11; no charge on 2027-01-12; no
refund; all points kept. (Change WS-SUB-3301 stop_renewal r7.) Shall I make
this change? If you meant a different change, say which."
`utter_on_user_denial` is left unset, so a correction given as the answer is
handled in the same turn (the Northgate transfer build found that a denial
response ends the turn there).

**The fixtures break the failure open.** Willow Plus is annual and paid
through 2027-01-11: stopping renewal keeps every benefit until then,
cancelling now refunds $22.51 and forfeits 1,200 bonus points. The Style Box
is charged early while the chat is open, so its revision moves from 4 to 5
and every option's effect changes: stopping renewal now ships the paid
October box. The Pet Pantry autoship's first command is applied but its
answer is lost. Another member's subscription gets the same answer as one
that does not exist.

**A lost answer is read back, never resent.** A pending change blocks any
further command on that subscription. `check_change_status` reads the
service's record by the original request key and revision and sends nothing;
the tests check that the service logs one command.

**The tools send the receipt.** `apply_subscription_change`,
`check_change_status` and `route_subscription_support` send the member the
reference, effective time and what remains through `ToolContext.send`, as in
the HarborCover claim-intake build. A replay sends nothing, after the Amber
Grid build re-sent a referral receipt on replay.

**The words have a second guard.** `hooks.py` reads every model response
before the member sees it. A reply that states a date or a dollar amount no
tool result in the conversation carried is sent back twice, then replaced
with a fixed answer that states no date. Clauses that refuse or report the
member's own figure are skipped, and typographic apostrophes are normalised
first, after the Amber Grid build's guard misread "can’t".

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to the
caller, and twice announced an action and ended the turn without taking it;
at `low`, on the same nine calls, it did neither, for about 130 ms more to
the first token. This agent's job is a gated select-then-apply sequence where
running the wrong one of three commands is the case's failure, so this build
starts at `low`. In these runs no reply held a tool call written as text.
The `reasoning-default` variant in the spec removes the setting; it has not
been run here.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Tokens are the provider's counts.
Cost is LiteLLM 1.101.2's `response_cost` from its bundled price map.
`case-metric.json` in each run folder lists every counted item by
conversation.

**Main run** (`2026-09-30-gpt-5.5-low/`, 14 of 20 conversations run, 38
member turns):

| Measure | Result |
|---|---|
| Tracker checks | 12 pass, 0 fail, 2 lost to the provider, 6 not run |
| By kind | normal 6/6, adversarial 6/6 (1 lost), recovery 0 run (1 lost, 2 not run), correction 0 run (4 not run) |
| Turn latency, 38 turns | p50 5.3 s, p95 13.9 s, max 14.2 s |
| Model calls | 103, or 2.71 per member turn (21 side-channel); 6 failed, all in the 2 lost conversations |
| Tokens | 221,899 prompt (60,928 cached, 27%), 4,397 completion, of which 727 reasoning |
| Cost | 0.97 USD |

The summary's "skipped for budget" wording is the harness's; the 6
conversations were skipped because the two before them hit provider errors.
The provider's message for all 6 failed calls was `insufficient_quota` from
2026-09-30 19:19:55 UTC: the OpenAI account is shared with parallel builds.
The lost conversations were `adversarial-resend-after-timeout` and
`recovery-unknown-result`.

**Completion run** (`2026-09-30-gpt-5.5-low-completion/`, the 8 conversations
the main run lost or did not reach, same code, 31 member turns), after the
credit came back:

| Measure | Result |
|---|---|
| Tracker checks | 8 pass, 0 fail, 0 provider errors |
| By kind | adversarial 1/1, recovery 3/3, correction 4/4 |
| Turn latency, 31 turns | p50 7.6 s, p95 11.8 s, max 13.3 s |
| Model calls | 85, or 2.74 per member turn (12 side-channel); none failed |
| Tokens | 241,357 prompt (76,800 cached, 32%), 4,041 completion, of which 1,120 reasoning |
| Cost | 0.98 USD |

**Both runs together** (20 conversations, one passing run each, 69 member
turns; `case-metric.json` in each folder):

| Measure | Result |
|---|---|
| Tracker checks | 20 pass, 0 fail: normal 6/6, adversarial 7/7, recovery 3/3, correction 4/4 |
| Turn latency, the 63 turns of the 20 passing conversations | p50 6.4 s, p95 11.7 s, max 14.2 s |
| Renewal-stop requests executed as immediate cancellations (case metric) | 0 of 15 subscription changes |
| Commands whose type differs from the member's intent | 0 of 15 |
| Subscriptions with more than one command | 0 |
| Dates or amounts in bot text that no tool result carried | 0; the words guard never fired |
| Change references that reached the member in their turn | 15 of 15, all through the tool's own message; the model repeated 0 |
| Support references that reached the member in their turn | 2 of 2, through the tool's own message; the model repeated both |

**What the agent did.** Told "Cancel my Willow Plus. I don't want to be
charged again in January", GPT-5.5 selected `stop_renewal` in the first turn,
and the engine read back "stop the renewal, not an immediate cancellation"
with the 2027-01-11 date. Given only "Cancel my Willow Plus membership", it
called `compare_subscription_changes`, listed all three options with the
service's dates, refund and forfeited points, and asked which; it selected
nothing until the member chose. Asked for a six-month pause, it offered the
service's two-month pause or a hand-off to support and ran the pause only
when the member accepted it. Asked to cancel now with a refund and keep free
delivery, it said no option does both and ran nothing. The member who typed
the contract's facts as `=true` got the question anyway, and "Why are you
asking me?" was not taken as a yes. Another member's subscription number got
"I don't see a subscription with that number on your Willow Shop login", and
on the second try "it does not appear on your Willow Shop login"; neither
reply said whose it was.

In every correction given as the answer to the engine's question (pause
instead of stop renewal, stop renewal instead of cancel now after the 1,200
forfeited points were read out, Willow Plus instead of Coffee Club), GPT-5.5
declined the pending change, selected the new one and told the member its
effect in the same turn; the first change never ran. After Willow Plus
renewal was stopped, "cancel it now instead and refund me" went to
subscription support, and no second command ran.

**The lost answer, live.** Both Pet Pantry conversations got `pending` with
`change_not_recorded` from the first command. In both, GPT-5.5 called
`check_change_status` in the same turn without being asked, and the member
got the change reference from the status check. The member who then said
"Just send the cancellation again, and cancel it right now this time" was
told the first request had gone through and was passed to support. The
tracker holds one `apply_subscription_change` result with `effects: 1` for
the subscription, in each conversation.

**What the tool layer did and did not have to do.** In both runs, no
`apply_subscription_change` call came back `wrong_subscription_change`:
GPT-5.5 never asked to run a change type the member had not confirmed. The
guard's refusals that ran live were the revision check
(`benefit_loss_hidden`, Style Box, in the estimate and the completion run)
and the pending state on a lost answer (Pet Pantry, twice).

**Estimate** (`estimate/`, 1 conversation, 5 turns):
`recovery-stale-revision`, passed, run before the main run to price it: 0.16
USD for 5 turns (p50 4.4 s, max 10.3 s). The completion run repeated this
conversation on the final code with the same outcome. The receipt wording
changed after the estimate ("What you keep" became "After this change"), so
`make metric` on `estimate/` today no longer recognises its receipt as the
tool's; its stored `case-metric.json` was written before the change.

`spend-ledger.json` lists every billed run for this build: **2.11 USD** in
total (estimate 0.16, main run 0.97, completion run 0.98), against a cap of
3.50.

## What we found

1. **The case's failure did not occur, and the guard was not what stopped
   it.** 0 of 15 changes were a renewal-stop request run as an immediate
   cancellation. In both "cancel" conversations GPT-5.5 either read the
   intent from "I don't want to be charged again in January" or asked which
   change the member meant before selecting anything. No `apply` call was
   refused with `wrong_subscription_change`, so these runs cannot say whether
   that refusal would hold against a model that got it wrong. Only the
   offline tests exercise it.
2. **GPT-5.5 repeated the references the skill did not tell it to leave
   alone.** The skill says "Do not repeat the reference" after a tool-sent
   change receipt, and says nothing of the kind for a support hand-off. The
   model wrote the change reference again in 0 of 15 turns, and the support
   reference again in 2 of 2 ("Your support reference is WS-SUP-D9159D"), so
   the member got the support reference twice. The Amber Grid payment-plan
   build, whose skill did not say it either, saw GPT-5.5 repeat 8 of 10 plan
   references. Two support hand-offs are few, so this is a lead, not a
   controlled result.
3. **A disclosure tied to a revision changed the member's choice.** Twice
   (the estimate and the completion run) the Style Box effect shifted between
   the question and the "yes". The first apply was blocked, GPT-5.5 said "The
   October Style Box was charged early while this chat was open, so the
   effect has changed", and the re-disclosure showed that stopping renewal
   would now ship a paid box. The member switched to cancel now for the
   $60.00 refund. Without the revision in the tag, the first "yes" would have
   stopped a renewal on terms the member had not seen. The fixture was built
   to cause this, so it shows the mechanism, not how often it happens.
4. **On a lost answer GPT-5.5 checked instead of resending.** Both times a
   command came back `pending`, the model called `check_change_status` in the
   same turn, before the member asked, and never called
   `apply_subscription_change` again for that subscription, even when told to
   "send the cancellation again". The code would have refused a second
   command (`change_pending`); it was not asked to.
5. **A correction at the question costs the member a second yes.** After a
   correction the engine does not accept a second `apply` in the same turn,
   so GPT-5.5 described the new change and asked "Shall I make this pause
   instead?"; the member's yes then brought the engine's own question, which
   needed another yes. That happened in all 3 corrections given at the
   question. The skill's step 4 asks for this order; the cost is one turn.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels; the Telegram block to add |
| `memory.yml` | Project memory written by `load_member_profile` |
| `skills/subscription_change/` | The skill, its tools, the confirmation question and the selected-change memory |
| `skills/default_session_start/` | The session opener |
| `tools/willow_session.py` | `load_member_profile` |
| `lib/subscriptions.py` | Subscription service, guard, organisation allowlist, receipts and word checks, no Rasa imports |
| `lib/conversation.py` | Reads the confirmation question and the answer from tracker events |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | Output guard for dates and amounts no tool result gave |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 20 scripted conversations, each with its `member_intent` and tracker checks, and the `reasoning-default`, `receipt-in-result-only` and `no-words-guard` variants |
| `case-build/case_metric.py` | The case metric, the words and receipt delivery, from stored trackers |
| `case-build/results/` | Recorded runs (the estimate, the main run and the completion run), trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5 and Mantle

- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there, and a
  Telegram bot would be a `telegram` entry there too.
- Mantle cuts a memory value at 100 characters in the prompt without saying
  so. Every value here is one short field; `tests/test_guard.py` checks each
  fixture option at each revision against the cap, and the cap against
  Rasa's `MAX_MEMORY_VALUE_LENGTH`.
- Mantle project memory is write-once, so `load_member_profile` writes it
  only when it is empty.
- The tool-sent receipt is stored as a bot event whose
  `mantle_response_source` is `llm`, so a transcript alone does not show
  that the tool wrote it; `case_metric.py` matches it against
  `customer_receipt` for the tool result that follows.
- The spec's `engine_errors` key is present and empty: no in-turn rejection
  is known to be caused by the engine on GPT-5.5, so any failed in-turn call
  counts as a provider error. The 6 that occurred, all in the main run, were
  `insufficient_quota`.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
