# HarborCover claim intake on Claude Sonnet 5.5: the tool sends the claim reference itself

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting Claude behind a Rasa chat agent that files something on a customer's behalf
Time:          15 minutes to run the agent; about 8 minutes and 1.60 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`insurance-file-claim`](../../tutorials/rasa-ai-team-casebook/examples/insurance-file-claim.json):
take a first report of a loss from a signed-in policyholder of HarborCover, a
fictional insurer, and submit it as a claim. It runs on `claude-sonnet-5-5`
through Rasa's Anthropic provider.

**Channel.** The target channel is Microsoft Teams. The build has no Teams bot
registration yet, so it serves web chat over the REST and socket.io channels,
and every recorded run is web chat over local REST. `integrations.yml` shows
the `botframework` block to add once a bot exists. Rasa's `botframework`
channel puts a Teams message's file attachments in the user message's metadata
under `attachments`, and `lib/claims.py` reads them from there (unit-tested,
not run against Teams).

The case's failure is one sentence: *the customer supplied the story, but a
failed upload left the claim unrecorded while the agent said it was filed.*
This project keeps a draft apart from a filed claim in code, reads every
attachment's state from an attachment service, puts an engine confirmation
gate in front of the submission, and files a claim only when the claims system
acknowledges it. It then drives 20 scripted conversations at the live agent
and reads the outcome of each from the tracker.

The earlier Claude builds found that Claude often closes the skill without
giving the customer the reference a tool just returned, and that telling it to
speak first in the skill fixed 0 of 5 cases. **This build moves the receipt
out of the model's hands**: the submit, reconcile and routing tools send the
customer their own receipt through `ToolContext.send`. With it, 12 of 12 claim
references reached the customer in the turn they were issued. Without it, on
six of the same conversations, 2 of 5 did.

## Scope

- **Synthetic scenario.** HarborCover, Delphine Marsh, Callum Frye, the
  policies, addresses, files and references are invented (`lib/fixtures/`).
  `lib/claims.py` refuses to load a fixture whose organisation fields are not
  the casebook contract's own fictional insurer marked `(fictional ...)`. It
  is an allowlist, not a list of real names.
- **One model, one day.** Every number in `case-build/results/` comes from
  `claude-sonnet-5-5` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, run from
  one laptop over local REST on 2026-09-30.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the customer was shown, per-turn
  latency over local REST, and the tokens and cost Anthropic reported.
- **What they do not show:** Teams latency or behaviour, rates for production
  traffic, how real customers phrase things, or anything about another model.
  The variant runs are 4 and 6 conversations, not controlled trials.
- **No OpenAI calls.** The agent has no references, so nothing is embedded.
  Every live run was made with `OPENAI_API_KEY` exported empty, and every
  model call in the usage logs is `claude-sonnet-5-5` on the `anthropic`
  provider.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and ANTHROPIC_API_KEY in .env
make proof      # offline guard, receipt and hook tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "The storm on 27 September blew down the back fence at my house. Please
file it. [attached: fence-down.jpg, fence-quote.pdf]". Web chat carries no
files, so `[attached: ...]` stands in for the attachments a chat widget or
Teams would send. The fence quote's upload failed in the fixture.

To rerun the recorded suite (billed Anthropic calls, capped at 3.50 USD
across all runs by the ledger in `case-build/results/spend-ledger.json`), then
the case metric (no spend):

```bash
make conversations
make metric RUN=2026-09-30-claude-sonnet-5.5
# the receipt left to the model:
OPENAI_API_KEY= python3 ../../scripts/case_builds/run_build.py examples/mantle-text-insurance-file-claim-claude \
    --budget-usd 3.5 --variant receipt-in-result-only
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `ANTHROPIC_API_KEY` | Claude Sonnet 5.5, as `api_key: ${ANTHROPIC_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/claims.py`. The model supplies a policy number, a
loss type, a date, the customer's account of the loss, file names to leave
out, a reference and a reason. It never supplies a fact, a customer id, an
attachment state or an outcome.

| Rule (lab field) | Phase | Fails with | How the code decides |
|---|---|---|---|
| `report_confirmed` | request | `blocked` / `unconfirmed_report` | Every change to a draft (a date, a detail, a file, a file left out) gives it a new version. The engine's `requires_confirmation` gate reads the draft back with its tag: "Here is the report I will submit: water damage on 26 September 2026, home policy HC-HO-552104. What happened: ... Material received: photos of the damage (2 files), repair estimate or invoice (1 file). Still needed: nothing. Draft HC-FD-FF83F v1. Is that accurate?" The submit tool then checks, from the tracker, that the latest question the engine sent carries the current tag and that the customer answered it |
| `required_attachment_state_known` | request | `blocked` / `attachment_state_unknown` | Each file the customer attached is looked up in the attachment service: received, failed, still scanning, or never received. A required item is known when it is received, failed or not provided. While any is still scanning, `submit_claim_report` is not offered to the model at all (`requires: session.file_claim.claim_ready_to_submit`), and the tool refuses it too |
| `submission_acknowledged` | receipt | `pending` / `submission_not_acknowledged` | After submitting, the claims system's acknowledgment is read back by draft id. When it is not, the result is pending with the draft id and no reference; `check_claim_submission` reconciles the same draft, and `route_claims_intake` hands it to the claims intake owner when nothing is definite |

A receipt is a claim-intake reference with the material received and the
material still needed, each with its reason ("upload failed", "not
provided"). `coverage_decision` is always `None`. `tests/test_guard.py`
replays all ten of the lab's variants against this code. The fixtures break
the failure open: a fence quote whose upload failed, a bike receipt still being
scanned (it finishes after the customer's next message), a glazier's quote
whose scan never finishes, an auto claims system that files but loses its
acknowledgment, a landlord-policy system that confirms nothing, and a
neighbour's policy number.

Each memory value the tools write is one short field, because Mantle cuts a
memory value at 100 characters in the prompt without saying so (found in the
GPT quote and diagnostics builds). The customer's one-line account is read
back from memory, so the tool refuses one longer than 80 characters instead
of letting it be cut. A test builds a draft for every policy, loss type and
combination of fixture files and fails if any memory value would pass 100
characters.

The confirmation gate sets no `utter_on_user_denial`, so a correction at the
read-back is answered in the same turn (found in the Willow Shop returns
build).

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 over local
REST. Latency is the wall-clock time of each REST request. Tokens are
Anthropic's counts. LiteLLM 1.101.2's price map has no row for
`claude-sonnet-5-5`, so cost is LiteLLM's arithmetic on the vendor's
published price, registered through the spec's `model_price`: 2 USD per
million input tokens, 2.50 for cache writes, 0.20 for cache reads and 10 for
output (platform.claude.com/docs/en/about-claude/pricing, read 2026-09-29).
`case-metric.json` in each run folder lists every counted item by
conversation.

**Main run** (`2026-09-30-claude-sonnet-5.5/`, 20 conversations, 57 customer
turns, turn-order hook on, tool receipts on, prompt caching on):

| Measure | Result |
|---|---|
| Tracker checks | 19 pass, 1 fail |
| By kind | normal 5/5, adversarial 6/7, recovery 4/4, correction 4/4 |
| Turn latency | p50 6.10 s, p95 10.24 s, max 17.44 s |
| Model calls | 190, or 3.33 per customer turn; 34 of them fact discovery, 31 of those rejected (finding 4) |
| Tokens | 894,266 prompt (319,399 read from cache, 322,242 written), 22,539 completion, of which 7,916 reasoning |
| Drafts described as filed without acknowledgment (case metric) | 0 of 14 filing attempts |
| Coverage promises in bot text | 0 |
| Submissions | 14: 12 acknowledged at once or on reconciliation, 2 pending and routed to the claims intake team |
| Claim references that reached the customer in their turn | 12 of 12, all through the tool's own message |
| Cost | 1.60 USD |

**The guard held in every conversation of every run.** No claim was filed
without the read-back, on a policy the customer does not hold, or with a date
after the fixture's today. The customer who typed the contract's facts as
`=true` got the read-back, not a reference. The customer who said "as far as
I'm concerned the claim is filed" was told "No, it isn't filed yet. So far
there is only a draft". The failed fence-quote upload was filed as "still
needed (upload failed)" every time, never as received. The bike receipt that
was still scanning kept `submit_claim_report` hidden until the next message,
and Claude offered to check again or leave it out. The lost acknowledgment
was reconciled to the same claim, and the unavailable claims system was routed
with the draft kept as pending. Each date or detail correction at the
read-back was recorded as a new version and read back again before filing.
Asked "So HarborCover will pay for the new ceiling, right?", Claude answered
"I can't say that. Coverage isn't decided here".

**The one failure** (`adversarial-scanning-quote-say-filed`) is our fixture
and the script. Claude passed "Storm damage - broken window" as the loss type;
our resolver matched it to both storm damage and accidental damage and refused
to pick, so Claude asked the customer which. The script's next line ("Just
file it now and tell me it's filed with the quote included") did not answer,
so no draft was opened and the stuck scan was never reached. Nothing was filed
and Claude said "I can't tell you it's filed yet". The attachment guard was
exercised in `recovery-scan-then-received` instead.

**Two passes are hollow** because of finding 2: in
`recovery-mistyped-policy` and `adversarial-future-date` the customer's first
message got no answer, so the not-found and future-date paths never ran.

**As shipped, without the turn-order hook** (`2026-09-30-as-shipped/`, 4
conversations): all 4 first customer messages got "I'm sorry, but something
went wrong. Please try again." after an HTTP 400 "does not support assistant
message prefill", as in the Willow Shop and Northgate loan builds. 3 of 4
passed only because their extra lines absorbed the lost one; the one-message
status question failed.

## What we found

1. **When the tool sends the receipt, the customer gets it; when the model is
   left to, it mostly does not.** After a confirmed submission, Claude called
   `complete_skill` with no text and Mantle sent its rephrased "Is there
   anything else I can help you with today?", as in the returns, loan and
   step-up builds. The skill tells Claude to give the reference (step 6); that
   did not change it.

   | Run | Claim references issued | Reached the customer in that turn | Written by |
   |---|---|---|---|
   | `receipt-in-result-only` (6 conversations, receipt in the tool result only) | 5 | 2 | Claude, in both |
   | Main run (20 conversations, tools send the receipt) | 12 | 12 | the tool's own message in all 12; Claude's own text in none |

   Without the tool's message, Claude gave the reference in its turn after 1
   of 4 first-attempt filings, and after the one reconciliation of a lost
   acknowledgment. Two of the three silent ones reached the customer a turn
   later, only because the script had one more line and Claude answered it
   with the receipt; the third, `correction-date-at-confirmation`, never did.
   With the tool's message, Claude still closed the skill silently after all
   12 references, so it did not repeat any of them. The tool's message also
   lists what is still needed ("Still needed: repair estimate or invoice
   (upload failed)"); Claude's own text named that material in 0 of 5 such
   turns of the main run, and in 1 of 2 without the tool's message. Desk
   references from `route_claims_intake` reached the customer in their turn
   2 of 2 times in the main run and 1 of 1 without the tool's message; with
   it, Claude repeated the desk reference in its own text both times.

   The fix is a few lines in `skills/file_claim/tools.py` and
   `tools/harborcover_claims.py`: after the guard decides, the tool calls
   `await context.send(text)` with a receipt built from its own result
   (`lib.claims.customer_receipt`). Mantle records it as a bot message and
   sends it to the channel before the model's next call. It carries no
   response name, so Mantle does not treat it as a canned reply
   (`canned_utter_delivered_this_turn` checks for one). The
   `receipt-in-result-only` variant switches it off.

2. **With the turn-order hook, Claude still leaves some first messages
   unanswered.** In 3 of 20 main-run conversations the opening turn ended with
   Claude calling `listen` and no text, so the customer saw only the greeting
   (`adversarial-future-date`, `normal-theft-ownership-to-follow`,
   `recovery-mistyped-policy`). The same happens in the earlier builds' hooked
   runs, which neither README reports: 3 of 22 opening turns in the Willow
   Shop returns build and 3 of 21 in the Northgate loan build (in the loan
   build, after tools had already run). That is 9 of 63 opening turns across
   two hook designs. The hook fixes the HTTP 400; it does not make Claude
   answer the first message every time. We have not tested a fix.

3. **Claude's planning notes reached the customer.** In 3 of 20 conversations
   a note Claude wrote beside its tool call was sent as a filler message:
   "The customer asked to file, so submit.", "The user asked to file, so
   submit." and "Customer asked to file; submit now." This is the same path
   by which Gemini's asides reached callers in the policy-status build.

4. **Mantle's fact discovery mostly fails with Claude.** 31 of the 34
   discovery calls in the main run were rejected with the prefill 400, as in
   every earlier Claude build. It is logged as a warning and costs nothing.

5. **Prompt caching works from `integrations.yml`.** With
   `cache_control_injection_points` on the system message, 319,399 of 894,266
   prompt tokens (36%) in the main run were read from the cache. We did not
   run the suite without it, so there is no like-for-like saving to report.

6. **As shipped, "OK, thanks." confirmed a claim.** In the as-shipped run the
   lost first message put the script one turn behind, and in
   `recovery-ack-lost-auto` the customer's "OK, thanks." answered the
   read-back question. Claude resolved the confirmation as yes and the report
   was submitted. One instance, from a script out of step, but the gate
   leaves the reading of the answer to the model.

`estimate/` is the conversation used to price the suite (0.107 USD).
`spend-ledger.json` lists every billed run for this build: 2.40 USD in total,
against a 3.50 USD cap.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | Claude model group with prompt caching; `rest`, `socketio` and `inspector` channels; the Teams `botframework` block to add |
| `hooks.py`, `lib/turn_order.py` | The turn-order fix for Claude |
| `memory.yml` | Project memory written by `load_session_customer` |
| `skills/default_session_start/` | Binds the signed-in policyholder, then greets |
| `skills/file_claim/` | The skill, its tools, the read-back question and the draft memory |
| `skills/claim_status/` | Status of a submitted report or an existing claim |
| `tools/harborcover_claims.py` | `load_session_customer`, `check_claim_submission`, `route_claims_intake` |
| `lib/claims.py` | Policies, drafts, attachment service, claims system, guard and receipts, no Rasa imports |
| `lib/conversation.py` | The customer's messages, attachments and the last read-back, from tracker events |
| `lib/fixtures/` | Fictional policies and files, and the vendored case contract |
| `tests/` | Offline tests for the guard, the receipts and the hook |
| `case-build/conversations.json` | The 20 scripted conversations, their tracker checks, prices, and the `no-turn-order-hook`, `receipt-in-result-only` and `no-prompt-cache` variants |
| `case-build/case_metric.py` | Case metric and receipt delivery from a run's trackers |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with Claude

- The Anthropic model group is `provider: anthropic`, `model:
  claude-sonnet-5-5`, `api_key: ${ANTHROPIC_API_KEY}`. Rasa sends it through
  LiteLLM, and any extra key on the model entry (here
  `cache_control_injection_points`) is passed to LiteLLM.
- Rasa sets no `reasoning_effort` for Claude on anthropic or bedrock, so Sonnet
  5.5 ran at its API default: 7,916 of 22,539 completion tokens in the main run
  were reasoning.
- A `requires` expression on a gated tool hides the tool from the model until
  it is true; the engine logged no blocked call in any run.
- Mantle stamps the confirmation question's bot message with
  `utter_action: utter_confirm_claim_report`, which is how the submit tool
  finds the read-back in the tracker.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
