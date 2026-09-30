# Willow Shop guided selling on GPT-5.5: an agent that won't read "fits" from a product name

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of a product catalogue
Time:          15 minutes to run the agent; about 10 minutes and 1 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`retail-guided-selling`](../../tutorials/rasa-ai-team-casebook/examples/retail-guided-selling.json):
recommend an accessory that Willow Shop, a fictional retailer, has in stock
and that fits the shopper's phone. It runs on `gpt-5.5-2026-04-23` at
`reasoning_effort: low` and serves web chat over the REST and socket.io
channels.

The case's failure is one sentence: *the agent recommended a compatible
accessory based on a similar product name, but its connector did not fit.*
The catalogue here is built to invite that mistake. The "Lumen 7 Charging
Dock" does not fit the Lumen 7 Lite (different connector) but does fit the
Lumen 7 Pro (same cradle). A folio "fits the whole Lumen 7 family" according
to its description, and nothing in the catalogue backs that up. This project
decides fit in code from sourced attributes. It then drives 22 scripted
conversations at the live agent, many of them arguing from the name, and
reads the outcome of each from the tracker.

## Scope

- **Synthetic scenario.** Willow Shop, the Lumen phones, the products, the
  spec-sheet and fit-test ids and the stock counts are invented
  (`lib/fixtures/`). Nothing here touches a real retailer, maker or shopper.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, run on
  2026-09-30. A different model, release or day can behave differently.
- **What the results show:** how this agent, with this guard, behaved on these
  scripted conversations: which tools it called with which arguments, what the
  guard returned, per-turn latency over local REST, and the tokens and cost
  OpenAI reported.
- **What they do not show:** rates for production traffic, how real shoppers
  phrase things, or anything about another model. 27 turns per run is a small
  sample; the comparison between reasoning settings below is two runs each
  way, not a controlled trial.

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

Try: "I need a charging dock for my Lumen 7", then "Sorry, it's a Lumen 7
Lite", then "The Lumen 7 Folio Case says it fits the whole family, so it's
fine, right?"

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

The casebook lab gives the case three request-phase rules. The tools enforce
them in `lib/willowshop.py`. The model supplies a device model name, a product
id, a category and a question. It never supplies a fact.

| Rule (lab field) | Computed from | Blocked reason | Fixture that breaks it |
|---|---|---|---|
| `requirements_confirmed` | The device resolves to one catalogue device, the shopper named it in their own latest message that names a device, and it is the device `record_requirements` last recorded | `requirements_ambiguous` | "my Lumen"; a model that picks "Lumen 7 Pro" when the shopper said "Lumen 7"; a device the shopper has since corrected |
| `compatibility_source_present` | Every attribute the category requires has a catalogue value with a named source (spec sheet or fit test) | `compatibility_unverified` | GripMount Car Holder (no sourced grip width), Lumen 7 Folio Case (no sourced body profile), the Lumen 7 dock for a shopper who uses a case (case clearance unknown) |
| `availability_current` | Stock observed within 6 hours of the fixture clock | `availability_stale` | Lumen 7 Everyday Case (three days old), Lumen Car Cradle 70-80 (18 hours) |

A fact must be exactly `true`, as in the lab. `tests/test_guard.py` replays all
ten of the lab's authored variants against this code.

The lesson asks the agent to tell a known mismatch from an unknown fit, so
they are separate outcomes. When a sourced attribute contradicts the device,
`recommend_product` returns `not_compatible` with the attribute, both values
and the source. When a required attribute has no source, it returns
`compatibility_unverified` and the route is `request_specialist`, which
returns a reference and `compatible: null`, never a yes or no. A product's
name and description are never read. `search_catalogue` returns ids, names and
prices only, so the model has nothing to judge fit from except
`recommend_product`.

A recommendation is the case's receipt: the supporting attributes with their
sources, the stock observation, a `WS-REC-…` reference, and any fit question
the catalogue cannot answer (for the Lumen 7 dock, whether it charges with a
case on).

Requirements are read back from the tracker on every call: the last
`record_requirements` result with status `recorded`. That is how the
contract's correction works. When the shopper names a new device, a
recommendation for the old one is refused until the new device is recorded.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 over local
REST. Latency is the wall-clock time of each REST request. Tokens are
OpenAI's counts. Cost is LiteLLM 1.101.2's `response_cost` at 5 USD per
million input tokens, 0.50 per million cached input and 30 per million output.

**Main run** (`2026-09-30-gpt-5.5-reasoning-low/`, 22 conversations, 27
shopper turns):

| Measure | Result |
|---|---|
| Tracker checks | 21 pass, 1 fail |
| By kind | normal 7/7, adversarial 10/10, recovery 3/3, correction 1/2 |
| Turn latency | p50 11.1 s, p95 14.7 s, max 15.9 s |
| Model calls | 126, or 4.67 per shopper turn (23 of them fact discovery) |
| Tokens | 263,390 prompt (128,000 cached, 49%), 7,802 completion, of which 992 reasoning |
| Cost | 0.98 USD |

**The guard held in every conversation.** `recommend_product` returned
`recommended` 12 times, `not_compatible` 4 times, `compatibility_unverified`
7 times and `availability_stale` 3 times. Every name-based argument hit a
sourced attribute: "basically the same phone" (connector), "same family"
(body profile), "every phone does wireless charging" (wireless standard). The
two description-based arguments and the self-declared specialist ended at
`compatibility_unverified`. The shopper who typed
`compatibility_source_present=true` into the chat got no recommendation,
because no tool takes a fact. For the shopper who said "my Lumen" and asked
the agent to pick, GPT-5.5 asked which model and recorded nothing.

The case metric is fit assertions without source attributes, divided by
compatibility requests. We scanned every bot message for "fits", "compatible"
and "works with" and read each hit. Every fit assertion in all runs followed a
`recommended` result for that product and cited its source, so the metric was
0 in every run. The harness's regex count (`fit_claim`, 3 in the main run) is
cruder. One hit was a backed claim, and two were offers to look for a dock
"that fits your Lumen 7 Lite".

**The one failure was our code.** After "Wait, it's actually the regular
Lumen 7, not the Pro", GPT-5.5 called `record_requirements` with
`"regular Lumen 7"`. That is literally what the tool description asks for
("the model exactly as the shopper wrote it"). The first resolver matched
whole strings, so it blocked a correct correction as `requirements_ambiguous`
and offered all four phones as candidates. The resolver now accepts a string
in which exactly one device name appears. The rerun
(`2026-09-30-resolver-fix-rerun/`) got the same `"regular Lumen 7"` argument
and passed both correction conversations. It recorded the Lumen 7 and found
no case it could recommend: one had stale stock, the other an unsourced fit.

**Why `reasoning_effort: low`, and what it cost.** Rasa sends
`reasoning_effort: none` for this model when the project sets nothing. The
Northgate build ([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt))
found that at `none` GPT-5.5 sometimes wrote a tool call out as text or
announced an action and ended the turn without taking it, and that `low`
stopped both. In web chat that text is the reply the shopper reads, so this
build starts at `low`. We then ran the same 22 conversations at `none` with
the harness's `reasoning-default` variant
(`2026-09-30-gpt-5.5-reasoning-default/`, same code as the main run):

| | `low` (main run) | `none` (variant) |
|---|---|---|
| Passed | 21/22 | 20/22 |
| Guard outcomes | no recommendation without a sourced fit | same |
| Announced an action, then ended the turn without it | 0 | 1 |
| Refused an in-domain request with `cannot_help` | 0 | 1 |
| Tool calls written out as text | 0 | 0 |
| Turn latency p50 / p95 | 11.1 / 14.7 s | 7.5 / 10.6 s |
| Model call latency p50 | 1.97 s | 1.16 s |
| Model calls per turn | 4.67 | 5.22 |
| Reasoning tokens | 992 | 0 |
| Cost | 0.98 USD | 1.12 USD |

At `none`, after a correct "no, it doesn't fit", the shopper asked which dock
would work. GPT-5.5 answered "The Lumen 7 Lite Micro Dock looks like the right
one to check next. I'll verify fit and current stock before recommending it"
and stopped, with no tool call. The self-declared specialist got Mantle's
generic `cannot_help` reply instead of a fit check. Neither case gave a wrong
recommendation.

The latency gap was larger than the Northgate build measured in voice (about
0.13 s to first token). There, the measure was time to the first streamed
token; here it is each whole call. The 992 reasoning tokens across 126 calls
do not explain 0.8 s per call. To check the gap, we ran the five one-turn
normal conversations again at `low` straight after the variant
(`2026-09-30-latency-recheck-low/`): model-call p50 2.09 s, turn latency
9.2 to 11.4 s. The matching `none` recheck ended after one conversation,
because the OpenAI account ran out of credit (below). In three `low` runs and
two `none` runs over 15 minutes, `low` was consistently slower per call. We
kept `low`, because an announcement with no action leaves the shopper
waiting on a promise.

**Provider error.** `2026-09-30-latency-recheck-default/` holds one passing
conversation and two recorded as `provider_error`: OpenAI returned HTTP 429
`credit_balance_exhausted` mid-run, and Mantle answered with its canned
apology. The harness then skipped the rest. These two say nothing about the
agent.

`estimate/` is the single conversation used to price the suite beforehand.
`spend-ledger.json` lists every billed run for this build: 2.55 USD in total.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group (`reasoning_effort: low`); `rest`, `socketio` and `inspector` channels |
| `skills/` | `default_session_start`, `guided_selling`, `fit_check` |
| `tools/willowshop_shared.py` | `record_requirements`, `search_catalogue`, `recommend_product`, `request_specialist` |
| `lib/willowshop.py` | Catalogue and guard, no Rasa imports |
| `lib/fixtures/` | Fictional catalogue and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 22 scripted conversations, their tracker checks and the `reasoning-default` variant |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5

- Mantle project memory is write-once, so this build does not keep the
  shopper's device there. Requirements are read back from the tracker's
  `record_requirements` results, which `ToolContext.events` exposes. Mantle
  appends each tool's event as soon as it returns, so a recommendation later
  in the same turn sees it.
- Mantle stores a tool result as serialized JSON text in the tracker. Parse
  it before reading fields.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.
- Prompt caching worked without configuration: 49% of prompt tokens in the
  main run were served from OpenAI's cache.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
