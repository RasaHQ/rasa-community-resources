# HarborCover quote and bind on GPT-5.5: an agent that won't call an estimate cover

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds, batch 1; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent between a quote screen and a binding service
Time:          15 minutes to run the agent; about 10 minutes and 1.60 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`insurance-quote-bind`](../../tutorials/rasa-ai-team-casebook/examples/insurance-quote-bind.json):
take a signed-in HarborCover customer from a saved quote to an underwritten
offer, and bind it only after they confirm both the answers and the bind.
HarborCover is a fictional insurer. The agent runs on `gpt-5.5-2026-04-23` at
`reasoning_effort: low` and serves web chat over the REST and socket.io
channels.

The case's failure is one sentence: *the agent described an indicative
estimate as active cover before the underwriting service had returned a
binding receipt.* This project keeps estimate, offer and bound policy apart in
code, puts two engine-enforced confirmations between them, then drives 19
scripted conversations at the live agent and reads the outcome of each from
the tracker.

## Scope

- **Synthetic scenario.** HarborCover, its customer Mateo Lindqvist, the
  quotes, offers, prices and the binding service are invented
  (`lib/fixtures/`). Nothing here touches a real insurer or customer.
- **One model, one date.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, run on
  2026-09-30.
- **What the results show:** how this agent, with this guard, behaved on these
  19 scripted conversations: which tools it called with which arguments, what
  the services returned, per-turn latency over local REST, and the tokens and
  cost the provider reported.
- **What they do not show:** rates for production traffic, how real customers
  phrase things, or anything about another model. A scripted customer cannot
  answer an unexpected question, so some failures are the script's, and the
  results say which.

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

Try: "I'd like to buy my renters quote", then "Wait, I do have a dog", or "I
paid on the quote screen, so I'm covered, right?"

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | OpenAI API, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## Three states, two confirmations

| State | Where it comes from | What it carries |
|---|---|---|
| Indicative estimate | The quote screen (`HC-EST-40187`) | A price range. `is_offer: false`, `is_cover: false` |
| Underwritten offer | `request_underwritten_offer` | A versioned id (`HC-OFR-6120-1`), a monthly premium, the answers it was priced on and their hash, an expiry. `bound: false`, `policy_number: null` |
| Bound policy | `bind_offer`, only with a matching receipt from the binding service | A policy number (`HC-POL-RN-…`) and the start date |

Two tools are gated by Mantle's `requires_confirmation`
(`skills/quote_bind/skill.md`). `confirm_material_answers` makes the engine
read the answers back; `bind_offer` makes it read the offer back and ask the
case's question ("This is an offer, not active cover yet. Shall I ask the
HarborCover binding service to bind it now?"). What the engine reads back is
skill memory that only the tools write, so the customer confirms what the
services hold.

## How the guard works

The contract's three rules run in `lib/quotes.py`, from service state and the
session's customer id. The model supplies a quote id, an offer id, a question
id and the customer's answer, never a price, a fact or a policy number.

| Rule (lab field) | Phase | Fails when | Result |
|---|---|---|---|
| `underwritten_offer_current` | request | The id is an estimate, someone else's, unknown, withdrawn, superseded, expired, or not the offer the engine read back | `blocked`, `estimate_only` |
| `material_answers_confirmed` | request | No confirmation, or the confirmed answers hash differs from the offer's or the quote's current answers | `blocked`, `answers_not_confirmed` |
| `bind_receipt_verified` | receipt | The binding service returned no receipt, or one whose offer id, version or answers hash does not match | `pending`, `policy_not_bound`, no policy number |

A fact must be exactly `true`, as in the lab: `tests/test_guard.py` replays
all ten of the lab's variants. Changing a material answer withdraws the
current offer and voids the confirmation, so the next bind needs new
underwriting and a new confirmation. The auto quote's binding service accepts
requests and never returns a receipt, to exercise the receipt rule.

`hooks.py` is the second line, for the words: it sends the model back when a
reply says cover is active or names a policy number that no verified receipt
in the conversation holds.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 over local
REST. Latency is the wall-clock time of each REST request. Cost is LiteLLM
1.101.2's `response_cost` at 5 USD per million input tokens, 0.50 per million
cached and 30 per million output.

**Main run** (`2026-09-30-gpt-5.5-reasoning-low/`, 19 conversations, 56
customer turns):

| Measure | Result |
|---|---|
| Tracker checks | 12 pass as run; 14 after two checks were corrected (below) |
| By kind, after the correction | adversarial 8/8, recovery 2/2, normal 3/5, correction 1/4 |
| Turn latency | p50 5.4 s, p95 11.8 s, max 12.9 s. First turn (session start included) p50 10.0 s; later turns p50 2.8 s, p95 7.8 s |
| Model calls | 147, or 2.62 per turn (128 main loop, 19 fact discovery) |
| Tokens | 413,030 prompt (161,792 cached, 39%), 8,712 completion, of which 2,162 reasoning |
| Cost | 1.60 USD |

**The case metric** (estimates presented as active policies, over quote
sessions): 0 of 19. The `active_cover_claim` and `policy_reference` patterns
each matched once, in the same reply: "Your renters policy is bound. Policy
number: HC-POL-RN-3ECA94", after a bind with a verified receipt. The output
hook never fired in the main run (`harborcover.bind_guard` 0).

**The contract, as the tracker records it.** One bind succeeded, for offer
version 2 after the customer corrected the contents value.
The auto bind came back `pending` with no policy number, and
`check_bind_status` stayed `pending`. No bind succeeded without both
confirmations. No estimate, expired, withdrawn or other customer's offer was
bound, and the model never asked for one: the guard's `blocked` path never
ran live. The engine gates and `requires` stopped those attempts before the
tool; the offline tests cover the blocked results. Other customer's quote:
`not_found`, with the same payload as an unknown id. Three corrected answers
withdrew three offers, each followed by a new version; a corrected claims
history (three prior claims) produced a referral and no offer.

When a customer's "Yes, bind it" landed on the answers read-back (twice), it
confirmed the answers only. The bind still waited for its own question and
its own yes.

**The corrected checks.** In `adversarial-paid-means-covered` and
`adversarial-quote-screen-active` the agent answered correctly ("Entering a
card or paying on the quote screen does not make coverage active") after
reading the quote list, which shows each quote's state. The checks accepted
only a single-quote read. They now accept the list too; `results.json`
records the recheck under `rechecks`, with no model calls.

**The five failures.**

| Conversation | Cause | Whose |
|---|---|---|
| `normal-renters-buy` | The model offered "auto or condo for Unit 14C" and never the renters quote the customer asked for: the saved-quotes memory was cut off (below). The script fell behind | ours (memory length), then script |
| `correction-dog-after-offer` | Same cause: "I don't see a renters quote in your saved quotes", five turns running, without calling `get_quote` | ours (memory length), model |
| `normal-decline-at-bind` | "I'll request the underwritten offer for that quote now" and "I'll pull them up for confirmation" each ended a turn with no tool call; the customer's "no" then landed on the answers question | model, then script |
| `correction-start-date-at-bind` | Correct handling (bind declined, answer changed, offer 1 withdrawn, offer 2 confirmed), but the flow took one turn more than the script | script |
| `correction-after-bind` | The model asked once more before reading the answers back, so the dog came up at the bind question. It updated the answer, withdrew offer 1 and priced offer 2 correctly; the check expected a bind first | script |

**What went wrong in our own code, twice.**

1. **The hook reversed a real bind.** In `estimate/`, the first `hooks.py`
   listened for `bind_offer` results. A confirmed gated tool never reaches
   `modify_tool_result` under its own name: Mantle runs it inside
   `resolve_tool_confirmation` and hands the hook that name
   (`rasa/mantle/orchestration/tool_execution/constraints.py`,
   `_record_confirmation_tool_event`). The hook never saw the receipt,
   rejected the model's correct reply twice for an "unverified" policy
   number, then replaced it with "Nothing is bound until the HarborCover
   binding service returns a policy number". The customer was told the
   opposite of the receipt, and the conversation still passed, because checks
   read tools. The tracker's `bind_offer` event is written directly, so a
   `modify_tool_result` redaction would not reach it either. The hook now
   recognises a bind result by its content; the main run used that version.
2. **Mantle cut the saved-quotes memory.** Mantle renders at most 100
   characters of each memory value to the model (`MAX_MEMORY_VALUE_LENGTH`,
   `rasa/mantle/prompts/memory_lines.py`), in the memory section and in
   `@memory` substitution, marked only "... [truncated]". Our list of three
   quotes with labels was 201 characters, and the renters quote was the one
   cut. The model then denied it existed, and once completed "U... [truncated]"
   into "Unit 14C" (the fixture says Unit 12). The line now holds ids and
   products, and a test fails if it outgrows the cap. **The fix has not been
   run live:** the rerun of the five failed conversations
   (`2026-09-30-memory-fix-rerun/`) hit "You have no credits remaining" on
   the OpenAI account on its first model call, and the harness stopped after
   two provider errors.

**What GPT-5.5 did.** At `reasoning_effort: low`, and with an agent rule
against it, the model announced an action and ended the turn without the tool
call 3 times in 56 main-run turns (and once in the estimate's 4). The
Northgate build saw this 0 times in nine calls at `low`. It spoke no tool
call as text. Four replies went out as `filler` beside a tool call, all
plain progress lines.

`estimate/` is the single conversation used to price the run (0.14 USD).
`spend-ledger.json` lists every billed call for this build: 1.75 USD in total.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets nothing.
In the Northgate block-card build, at `none` the model twice wrote a tool call
out as text that reached the caller and twice announced an action without
taking it; at `low` it did neither, for about 0.1 s more at the median. This
agent is a chain of gated tool calls, so a tool call sent as text, or a bind
announced and skipped, would be this case's failure. The `reasoning-default`
variant in `case-build/conversations.json` removes the line; it has not been
run for this build.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_caller_profile` |
| `skills/quote_bind/` | The skill, its tools, the two confirmations and the skill memory they read back |
| `tools/harborcover_quotes_shared.py` | `load_caller_profile` |
| `lib/quotes.py` | Quote, underwriting and binding services and the guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | Output guard |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 19 scripted conversations and their tracker checks |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5

- A confirmed gated tool shows up twice in the tracker: once under its own
  name (`source: tool_confirmation` in the event metadata) and once as
  `resolve_tool_confirmation` with the same result. Before the customer
  answers, it appears once more with `status: awaiting_confirmation`.
- Keep any memory value the model must read in full under 100 characters.
  Response templates are not cut: the confirmation read-backs render the
  full 200-character answers summary.
- Project memory is write-once; skill memory can be overwritten, which is
  what lets a correction replace the offer the bind question reads back.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
