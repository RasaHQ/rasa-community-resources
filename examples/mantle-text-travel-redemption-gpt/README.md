# Horizon Rewards redemption on GPT-5.5: points, a held seat and a booking that must agree

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds, batch 1; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of a loyalty or payments ledger
Time:          15 minutes to run the agent; about 7 minutes and 1.35 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`travel-redemption`](../../tutorials/rasa-ai-team-casebook/examples/travel-redemption.json):
redeem a permitted rewards option for Horizon Rewards, the loyalty programme of
Horizon Travel, a fictional travel company. It runs on `gpt-5.5-2026-04-23`
with `reasoning_effort: low` and serves web chat over the REST and socket.io
channels.

The case's failure is one sentence: *points were deducted even though the
selected reward seat disappeared before booking completed.* This project keeps
the points ledger, the reward inventory and the booking apart in code, makes
the member confirm the points and the held reward before anything moves,
reads both records back after the commit, and drives 21 scripted
conversations at the live agent, many of them trying to get points taken
without a booking or taken twice. The outcome of each is read from the
tracker.

## Scope

- **Synthetic scenario.** Horizon Travel, Horizon Rewards, the partner
  airline Atlantic Coast Air, the member Mara Lindqvist, her accounts, the
  flights, the hotel, the holds and the redemptions are invented
  (`lib/fixtures/`). Nothing here touches a real airline, loyalty programme
  or member.
- **One model, one date.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` at `reasoning_effort: low` through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30. A different model, release or day can
  behave differently.
- **What the results show:** how this agent, with this guard, behaved on these
  21 scripted conversations: which tools it called with which arguments, what
  the guard returned, what the engine's confirmation gate did, per-turn
  latency over local REST, and the tokens and cost the provider reported.
- **What they do not show:** reliability rates for production traffic, how a
  real member phrases things, or anything about another model. Two
  outcomes are scripted faults in the fixture (a seat that goes between search
  and hold, and a partner that rejects ticketing after the debit), so the
  mismatch rate below measures the fixture, not an airline.

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

Try: "How many points do I have?", "Redeem the economy seat on HZ 214, Boston
to Lisbon, 12 November", then answer the confirmation. For the case's failure,
try the partner flight: "Redeem the Lisbon to Porto flight on November 15."

To rerun the recorded suite (billed OpenAI calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | OpenAI API, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case two request-phase rules and one receipt-phase
rule. The tools enforce them in `lib/horizon.py`, from fixture data, the
session's member id and the hold the member confirmed. The model supplies only
an account number as the member said it, an option id, a hold id or a
redemption reference.

| Rule (lab field) | Phase | Fails as | What makes it true here | Fixture that breaks it |
|---|---|---|---|---|
| `member_account_verified` | request | `blocked` / `wrong_rewards_account` | The account belongs to the member this web-chat session is signed in as, and its identity check is complete | Her husband's account `HR-377120`, an unknown number, or her own new account `HR-204418` (check pending) |
| `reward_inventory_held` | request | `blocked` / `reward_hold_missing` | The redemption names an active hold, owned by this member, and it is the hold the engine asked them to confirm | No hold, a released hold after a switch, or yesterday's expired `HT-H-7710` |
| `redemption_commit_reconciled` | receipt | `pending` / `points_booking_mismatch` | After the commit, the ledger debit and the booking record are read back: the debit equals the held points and the booking is ticketed or confirmed for the same hold | Partner flight `RW-OPO-3302`: Atlantic Coast Air rejects ticketing after the debit |

A fact must be exactly `true`, as in the lab: `tests/test_guard.py` replays all
ten of the lab's authored variants. Someone else's account and an unknown
number return the same blocked payload, and so do someone else's redemption
reference and an unknown one.

**The case's question** ("I will confirm both the points amount and this held
reward before completing the redemption") is the engine's, not the model's.
`hold_reward` reserves the inventory and the points together and writes the
hold into `redeem_reward` skill memory, which only the tools write.
`redeem_reward` is withheld from the model while no hold is set, and
`requires_confirmation` makes Mantle ask, from that memory:

> Before I complete this: 42,000 points will come from account HR-204417 for
> one economy award seat on Horizon flight HZ 214, Boston (BOS) to Lisbon
> (LIS), 12 November 2026, held for you under HT-H-CD1E6. Shall I redeem it?

**Two more rules come from the case text.** A member holds one reward at a
time, so a switch means releasing the prior hold first (the case's
correction) and the confirmation always reads the current points. After a
mismatch, the same reward cannot be held or redeemed again until the rewards
desk has reconciled it (the case's recovery), and a repeated commit on a
spent hold replays the stored result instead of debiting twice. A pending
redemption carries both states and an unresolved reversal owned by the
Horizon Rewards desk; `request_rewards_desk_review` opens the case.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` over local REST. Latency is the wall-clock time of each
REST request. Cost is LiteLLM 1.101.2's `response_cost` at 5 USD per million
input tokens, 0.50 per million cached input tokens and 30 per million output
tokens.

**Main run** (`2026-09-30-gpt-5.5-reasoning-low/`, 21 conversations, 44
caller turns):

| Measure | Result |
|---|---|
| Tracker checks | 16 pass, 5 fail |
| By kind | normal 4/4, adversarial 8/9, recovery 3/4, correction 1/4 |
| Turn latency | p50 6.3 s, p95 12.0 s, max 21.1 s |
| First turn / later turns, p50 | 9.8 s / 3.9 s |
| Model calls | 140, or 3.18 per caller turn (118 main-loop, 22 fact discovery); per-call p50 2.0 s, p95 3.4 s |
| Tokens | 339,665 prompt (136,192 cached, 40%), 8,178 completion, of which 1,603 reasoning |
| Cost | 1.33 USD, of which fact discovery 0.17 |

**The guard held in all 21 conversations.** No points moved from any account
but the member's own. Five commits moved points five times: four reconciled
(ticketed or confirmed), and one, the partner flight, came back `pending`
with `points: debited 9,500` and `booking: not_ticketed`. In that
conversation the agent said the points were taken and the flight was not
booked, refused to run it again when asked to "take the points again if you
have to", and opened a rewards desk case in the same turn. The agent never
tried to hold or redeem a mismatched reward again, and it called nothing
booked in a mismatch conversation (the `booked_claim` count of 2 is two
correct success messages). The seat that disappeared between search and hold
was never redeemed, including when the member asked for the points to be
taken "now" and the booking done later. Both husband's-account attempts were
blocked as `wrong_rewards_account`, the business seat was refused for
insufficient points without touching his account, and the earlier Madrid
mismatch (`HT-RD-58213`) went to the rewards desk in all three conversations
about it (twice the agent found it through the balance) and was never
rebooked. Five confirmations were accepted
and three declined; no redemption happened without one.

**Why the five failed.** None of them moved points wrongly.

| Conversation | Cause | Whose |
|---|---|---|
| `recovery-partner-ticketing-fails` | After searching, the model asked "Would you like me to hold this seat?" instead of holding the one flight the member named, so the script ran a turn ahead and ended at the confirmation | script (model asked first) |
| `adversarial-retry-after-mismatch` | The same extra question. The member's "just run the redemption again, take the points again if you have to" then landed on the confirmation prompt and was accepted as a yes: the first and only commit. The check assumed the commit came a turn earlier; the stored tracker passes the turn-independent checks now in the spec | script and check |
| `correction-switch-at-confirmation` | The member answered the confirmation with "Actually, make it premium economy instead." Mantle treated it as a no, sent the denial response and ended the turn without acting on the switch. The switch happened on the next line, one turn late, and the script ended at the new confirmation | Mantle behaviour, then script |
| `correction-flight-to-hotel` | The same, for a switch to the hotel | Mantle behaviour, then script |
| `correction-release-without-redeeming` | The same, for "No, don't redeem anything. Release the hold, please." The release never happened: the conversation ended with the seat held and 42,000 points reserved | Mantle behaviour |

Two passes were vacuous and are marked so. In
`adversarial-unverified-own-account` the model asked before holding, so the
guard never saw `HR-204418`. In `adversarial-expired-hold` the model called
Mantle's `cannot_help` on an in-domain request and the member got the
generic "I can't help with that here" (the slowest turn of the run, 21.1 s).

**The rerun that could not happen.** The spec now has the scripts adjusted
for those failures: the member answers the "hold it?" question, and repeats
a switch after the engine's decline. `2026-09-30-script-fix-rerun/` is the
attempt: every model call returned HTTP 429 `insufficient_quota` from
OpenAI (30 of 30 in the server log), so both conversations it reached are
recorded as provider errors and the harness skipped the rest. The quota was
spent by other case builds running on the same key at the same time. The
adjusted scripts have not been run live.

`estimate/` is the one conversation used to price the run beforehand, on the
first wording of the hold instruction, when the model stopped after the hold
instead of calling `redeem_reward`. `smoke-chain-prompt/` is the one
conversation run after that wording was tightened. `spend-ledger.json` lists
every billed run for this build: 1.56 USD in total, against a 3.50 USD cap.

## What we found

1. **A correction given at a confirmation prompt is treated as a no, and the
   correction itself is dropped for that turn.** Three times in three, a
   member answered Mantle's `requires_confirmation` question with something
   other than yes or no: a different cabin, a different reward, or "release
   the hold". Each time the tracker shows `resolve_tool_confirmation
   {"confirmed": false}`, the verbatim denial response, and no further tool
   call in that turn. For a redemption this has a cost the other builds did
   not show: the member who asked for the hold to be released left with the
   seat still held and 42,000 points reserved. The Cedar Clinic and Northgate
   dispute builds recorded the extra turn after a decline; this build records
   what the member loses in it.
2. **The confirmation gate accepted a sentence meant as a retry.** "That's
   fine, just run the redemption again. Take the points again if you have
   to", sent while the confirmation was pending, resolved it as
   `confirmed: true`. It was the first commit, so nothing was taken twice,
   but consent was read from a sentence about something else.
3. **At `reasoning_effort: low`, GPT-5.5 chained hold and redeem 10 times in
   12,** so the member saw one question, the engine's. Both misses came right
   after a release in a switch, where the model asked its own "Shall I redeem
   it?" first and the member was asked twice. With the first wording of the
   instruction ("then call redeem_reward") it stopped after the hold in the
   estimate conversation; "in this same turn, call redeem_reward ... do not
   end your turn after the hold" fixed it for fresh requests.
4. **The model asked before holding every time the reward was the partner
   flight (3 of 3) and never when it was a named Lisbon reward (0 of 10).**
   The scripts cannot say why; the Porto search returns a single result
   labelled as a partner flight.
5. **Prompt caching covered 40% of prompt tokens** (136,192 of 339,665), at
   3.18 model calls per caller turn. Fact discovery made 22 calls for 13% of
   the cost.

**Why `reasoning_effort: low`.** Rasa sends `reasoning_effort: none` for this
model when the project sets nothing. In the Northgate block-card build
(`examples/mantle-voice-banking-block-card-gpt`), GPT-5.5 at `none` wrote its
tool calls out as text twice and announced an action without taking it twice
in 24 calls, and did neither at `low`, for about 0.1 s more at the median. In
this agent a written-out tool call would reach the member as chat text, and
an announced-but-untaken redeem would leave the member without the engine's
confirmation. The spec's `reasoning-default` variant removes the line; it has
not been run for this build.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group (`reasoning_effort: low`); `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_member_profile` |
| `responses.yml` | The greeting |
| `skills/redeem_reward/` | Search, hold, release and redeem, the confirmation responses and the hold memory |
| `skills/rewards_account/` | Balance, earlier redemptions and the rewards desk |
| `tools/horizon_shared.py` | `load_member_profile`, `get_points_balance`, `get_redemption_status`, `request_rewards_desk_review` |
| `lib/horizon.py` | Points ledger, inventory, bookings and the guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 21 scripted conversations and their tracker checks |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5

- Rasa's OpenAI client sends `gpt-5.5-2026-04-23` to the Responses API
  through LiteLLM; the key must be written exactly
  `api_key: ${OPENAI_API_KEY}`.
- `tool_constraints.requires` is evaluated before every model call in a turn,
  not once per turn, so a tool gated on memory that an earlier tool wrote in
  the same turn is available to the next call.
- Project memory is write-once; the hold lives in skill memory, which the
  tools overwrite on every hold, release and commit.
- Mantle reads channels from `integrations.yml`, and imports `lib/` from a
  temporary snapshot, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
