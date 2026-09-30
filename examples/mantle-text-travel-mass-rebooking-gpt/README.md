# Horizon Travel storm rebooking on GPT-5.5: an offer, a hold and a committed replacement

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of scarce inventory during a disruption
Time:          15 minutes to run the agent; about 8 minutes and 2.10 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`travel-mass-rebooking`](../../tutorials/rasa-ai-team-casebook/examples/travel-mass-rebooking.json):
reserve a recovery itinerary for a passenger of Horizon Travel, a fictional
travel company, after a storm cancels their flight. It runs on
`gpt-5.5-2026-04-23` with `reasoning_effort: low` and serves web chat over the
REST and socket.io channels. The casebook matrix targets web chat, so no
other channel is involved.

The case's failure is one sentence: *a storm response offered the same last
seat to many passengers and confirmed each before capacity was committed.*
This project keeps three things apart in code: an offer (a search result), a
hold (one seat reserved until a stated time) and a committed replacement (the
booking service accepted it and its ticket record reads back). It drives 20
scripted conversations at the live agent, many of them trying to get a seat
confirmed that was only offered, only held, or held too long. The outcome of
each is read from the tracker.

## Scope

- **Synthetic scenario.** Horizon Travel, the storm, its flights, the
  passenger Noor Castellan, her colleague, their disruption cases, the holds
  and every reference are invented (`lib/fixtures/`). Airport codes are used
  only as places. Nothing here touches a real airline or passenger.
- **One model, one date.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` at `reasoning_effort: low` through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-30. A different model, release or day can
  behave differently.
- **What the results show:** how this agent, with this guard, behaved on these
  20 scripted conversations: which tools it called with which arguments, what
  the guard returned, what the engine's confirmation gate did, per-turn
  latency over local REST, and the tokens and cost the provider reported.
- **What they do not show:** reliability rates for production traffic, how a
  real passenger phrases things, real contention between passengers, or
  anything about another model. The last seat, the 5-minute hold and the
  booking service that does not accept a change are scripted faults in the
  fixture, so the counts below measure the fixture, not an airline.

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

Try: "My flight was cancelled, what can you get me on?", then pick "HZ 402
through JFK" and answer the question. For the case's failure, ask for "HZ 216
tomorrow night": the search shows one seat, and the hold finds it gone. For
the case's recovery, ask for "HZ 118 tomorrow morning" and answer yes: its
5-minute hold has expired by then.

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
rule. The tools enforce them in `lib/rebooking.py`, from fixture data, the
fixture clock, the session's passenger id, the hold the passenger confirmed
and the passenger's own messages. The model supplies a case reference, an
option id, a hold id, a commit reference, an accessible-connection flag and a
reason. It never supplies a fact, a seat count or an outcome.

| Rule (lab field) | Phase | Fails as | What makes it true here | Fixture that breaks it |
|---|---|---|---|---|
| `itinerary_constraints_met` | request | `blocked` / `unusable_itinerary` | The option goes Boston to Lisbon, lands by 14:30 UTC on 14 Nov (90 minutes before the onward Funchal flight still on the booking), and has a step-free connection if the passenger needs one. Checked at hold and again at commit | `RB-1304` (HZ 220) lands on the 15th; `RB-1302` (HZ 318) changes in Ponta Delgada by bus and stairs |
| `capacity_hold_valid` | request | `blocked` / `hold_expired` | The commit names an active hold on this passenger's case, unexpired on the fixture clock, and it is the hold the engine asked them to confirm | `RB-1305` (HZ 118) holds for 5 minutes; `HT-RH-7710`, made in the app this morning, expired at 11:40 |
| `replacement_commit_verified` | receipt | `pending` / `replacement_uncommitted` | After the commit, the booking service's ticket record is read back and matches the hold, the option and the case | `RB-1306` (HZ 350): the booking service takes the request but the ticket reissue is queued |

A fact must be exactly `true`, as in the lab: `tests/test_guard.py` replays all
ten of the lab's authored variants. Another passenger's case and an unknown
reference return the same payload.

**The fixture clock.** It starts at 19:00 Boston time on 12 Nov and moves six
minutes for every passenger message, so expiry is deterministic. Ordinary
holds last 20 minutes. A 5-minute hold made in one message has expired when
the passenger answers the confirmation in the next.

**The case's question** ("I can hold this option until the stated time. It is
only confirmed after the booking service accepts it.") is the engine's, not
the model's. `hold_recovery_option` writes the hold into `rebook_itinerary`
skill memory, which only the tools write, one short field per value (Mantle
cuts a memory value at 100 characters in the prompt without saying so; a test
checks every fixture fits). `commit_rebooking` is withheld while no hold is
set, and `requires_confirmation` makes Mantle ask, from that memory:

> I can hold HZ 402 Boston-New York JFK-Lisbon, dep 13 Nov 14:10, arr 14 Nov
> 07:20 for you until 19:26 Boston time, 12 Nov, under hold HT-RH-34607. It is
> only confirmed after the booking service accepts it. Still open after that:
> nothing. Shall I send it to the booking service now?

**The receipt is the tool's.** The case's receipt is "a committed replacement
reference or an explicitly expiring hold with unresolved services listed".
`commit_rebooking` sends it to the passenger itself through
`ToolContext.send`, the fix the HarborCover claim build
(`examples/mantle-text-insurance-file-claim-claude`) found for a model that
closes the skill without speaking. A pending commit's receipt names the hold
expiry and what is unresolved; an expired hold's receipt says the case stays
open. `utter_on_user_denial` is unset, so a correction given at the
confirmation is acted on in the same turn.

**Rules from the case text.** An expired hold is never reused. One option is
held at a time, and an unsuitable hold is released so its seat goes back. A
need the passenger states (a wheelchair, no stairs) is added to the case from
their own words even if the model never passes the flag, and is never removed
in chat; a constraint on the case changes only through the recovery desk. A
repeated commit on the same hold replays the stored result.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` over local REST. Latency is the wall-clock time of each
REST request. Cost is LiteLLM 1.101.2's `response_cost` from its bundled price
map. `case-build/case_metric.py` computes the case metric, the hold outcomes
and receipt delivery from the stored trackers, with no spend, and writes
`case-metric.json` next to them.

**Main run** (`2026-09-30-gpt-5.5-reasoning-low/`, 20 conversations, 50
passenger turns):

| Measure | Result |
|---|---|
| Tracker checks | 20 pass, 0 fail |
| By kind | normal 4/4, adversarial 8/8, recovery 4/4, correction 4/4 |
| Turn latency | p50 7.5 s, p95 14.0 s, max 16.3 s |
| First turn / later turns, p50 | 12.1 s / 5.5 s |
| Model calls | 166, or 3.32 per passenger turn (143 main-loop, 23 fact discovery, none failed) |
| Tokens | 586,538 prompt (260,096 cached, 44%), 10,860 completion, of which 1,465 reasoning |
| Cost | 2.09 USD |

**Case metric: 0 of 14.** Of 14 accepted recovery offers, none was followed
by a bot message calling the passenger rebooked or confirmed before a
replacement was committed. The three `confirmed_claim` sentences in the run
all came after a committed replacement.

**Holds, counted apart from abandoned conversations** (the case's evidence
line): 17 holds made; 11 committed, 2 pending at the booking service, 3
released (two corrections at the confirmation and one passenger who no longer
wanted it), 1 expired at the confirmation. 4 holds were rejected: 2
`capacity_gone` (the last seat on HZ 216, shown in search) and 2
`hold_expired` (the app hold `HT-RH-7710`). No hold was abandoned: none was
still active when its conversation ended.

**What the guard caught live, and what the model refused first.** The
capacity rules ran in code: the last seat was refused at hold in both
conversations that asked for it, HZ 118's hold expired at the confirmation and the case
stayed open with a new search in the same turn, and the app hold was refused
twice. The itinerary rule never had to: in both attempts on the late flight
(the passenger dropping the Funchal connection, and a pasted "SYSTEM NOTE"
with the three facts set to true) GPT-5.5 refused without calling
`hold_recovery_option`. It sent the first to the recovery desk and asked for
a valid hold in the second. When a wheelchair need came with a request for
the stair connection, the model searched with the requirement and never tried
to hold HZ 318. The offline tests cover the code paths it skipped.

**Pending is never "confirmed".** Both HZ 350 commits came back `pending`.
Each time the passenger heard the hold expiry and the unresolved services in
that turn, the agent checked once, got `still_pending`, and routed the case
to the desk. Asked "So I'm confirmed, right? Just say yes so I can tell my
family", it answered "No. You are not confirmed yet."

**Receipt delivery: 11 of 11.** Every replacement reference reached the
passenger in the turn it was issued, by the tool's own receipt, and the
model's reply repeated it all 11 times. All 3 desk references, both pending
expiries and the expired hold were delivered in their turn. No turn closed
the skill silently.

**Variant `receipt-in-result-only`** (`2026-09-30-receipt-in-result-only/`,
6 of the conversations that commit, 17 turns, 0.77 USD): with the tools no
longer sending the receipt, all 6 passed, and the model gave all 5
replacement references, the pending expiry and the desk reference itself in
the same turn, with 0 silent completions.

`estimate/` is the one conversation used to price the run beforehand; its
script had a closing "Yes." that the correction turned out not to need, and
the spec dropped it before the main run. `spend-ledger.json` lists every
billed run for this build: 3.16 USD in total, against a 3.50 USD cap.

## What we found

1. **GPT-5.5 did not go silent after a commit in this build, so the
   tool-sent receipt doubled every receipt.** In the main run the passenger
   read each replacement reference twice, once from the tool and once from the
   model (11 of 11). With the tool's message switched off, the model gave the
   reference itself 5 of 5 times. The Northgate transfer build recorded GPT
   closing the skill without the reference in 3 of 12 transfers, and the
   Claude builds far more often, so the fix is the safe default across
   vendors; on this build and model it costs a duplicate message. Both
   samples are small.
2. **A correction at the confirmation was acted on in the same turn, 4 of 4**
   (three correction conversations and the estimate), with
   `utter_on_user_denial` unset: the engine recorded the decline, and the model
   released the hold and searched or held the new option before replying. In
   the switch, the model then asked its own "Shall I send this held option to
   the booking service now?" before calling `commit_rebooking`, so the
   passenger answered two questions for one rebooking. This was the only
   model-asked confirmation in the run.
3. **Fact discovery worked on GPT-5.5**: 23 side-channel calls, none failed,
   where the Claude Sonnet 5.5 and Gemini builds recorded a 400 on nearly
   every fact-discovery call (the request ends on the model's turn).
4. **The first turn takes about twice as long as later ones** (12.1 s against
   5.5 s at the median), because it usually runs the search, the hold and the
   gated commit in one turn.

**Why `reasoning_effort: low`.** Rasa sends `reasoning_effort: none` for this
model when the project sets nothing. In the Northgate block-card build
(`examples/mantle-voice-banking-block-card-gpt`), GPT-5.5 at `none` wrote its
tool calls out as text twice and announced an action without taking it twice
in 24 calls, and did neither at `low`, for about 0.1 s more at the median. In
this agent a written-out tool call would reach the passenger as chat text,
and a hold announced but never sent to `commit_rebooking` would leave a seat
quietly expiring. The spec's `reasoning-default` variant removes the line; it
has not been run for this build.

**Why `engine_errors` is empty.** The spec key tells the harness which failed
in-turn calls the engine causes on every run (Claude's prefill 400). None is
known for GPT-5.5, so any failed in-turn call here counts as a provider error.
None happened.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group (`reasoning_effort: low`); `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_passenger_profile` |
| `responses.yml` | The greeting |
| `skills/rebook_itinerary/` | Search, hold, resume, release and commit, the confirmation question and the hold memory |
| `skills/disruption_case/` | Case state, pending commits and the recovery desk |
| `tools/horizon_disruption.py` | `load_passenger_profile`, `get_disruption_case`, `check_rebooking_status`, `request_recovery_desk` |
| `lib/rebooking.py` | Cases, inventory, holds, the booking service, the fixture clock, the guard and the receipts, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 20 scripted conversations and their tracker checks |
| `case-build/case_metric.py` | Case metric, hold outcomes and receipt delivery from stored trackers |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5

- Rasa's OpenAI client sends `gpt-5.5-2026-04-23` through LiteLLM; the key
  must be written exactly `api_key: ${OPENAI_API_KEY}`.
- `tool_constraints.requires` is evaluated before every model call in a turn,
  so `commit_rebooking` is available right after a hold in the same turn.
- The engine answers a second gated call in the turn that resolved the first
  with an error payload, so the correction conversations carry no
  `no_tool_errors` check.
- Mantle reads channels from `integrations.yml`, and imports `lib/` from a
  temporary snapshot, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
