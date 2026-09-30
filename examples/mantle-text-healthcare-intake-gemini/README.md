# Cedar Clinic pre-visit intake on Gemini: an eligibility check is not a promise of payment

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of patient intake and insurance checks
Time:          15 minutes to run the agent; about 12 minutes, 1.70 USD and 156 Gemini requests for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`healthcare-intake`](../../tutorials/rasa-ai-team-casebook/examples/healthcare-intake.json):
record the administrative details for a signed-in patient's upcoming visit at
Cedar Clinic, a fictional clinic, and check their insurance eligibility with
the payer, without ever telling them the visit will be paid for. It runs on
`gemini-3.1-pro-preview` and serves web chat over the REST and socket.io
channels.

The case's failure is one sentence: *an insurance lookup returned an
uncertain result, but the agent told the patient the visit would definitely be
paid for.* This project keeps intake completeness, the payer response and
payment assurance apart in code, puts an engine read-back in front of the
record, gives every open insurance question an owner before the intake can be
recorded, and has the tools send the patient their own receipts. It then
drives 15 scripted conversations at the live agent and reads the outcome of
each from the tracker.

## Scope

- **Synthetic scenario.** Cedar Clinic, the patient Nadia Farrow, the payers
  Larchmere Health Plan and Oakhollow Mutual Health, the member ids, phone
  numbers and references are invented (`lib/fixtures/`). The response codes
  (`EL-1`, `EL-42` and so on) are this build's own, not a standard's.
  `lib/intake.py` refuses to load a fixture whose organisation is not the
  casebook contract's own fictional clinic, or whose other organisation fields
  are not one of the two invented payers it allowlists, each marked
  `(fictional ...)`. It is an allowlist, not a list of real names.
- **Administrative only.** The agent handles contact phone and insurance. A
  clinical, symptom or medication question gets a route to the clinic's nurse
  line and nothing else; no tool reads or stores clinical content.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gemini-3.1-pro-preview` (a preview model) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run from one laptop over local REST on 2026-09-30.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the patient was shown, per-turn
  latency over local REST, and the tokens and cost the provider reported.
- **What they do not show:** rates for production traffic, how real patients
  phrase things, a real payer's eligibility service, or anything about another
  model. 15 conversations is a small sample.
- **No OpenAI calls.** The agent has no references, so nothing is embedded.
  Every live run was made with `OPENAI_API_KEY` exported empty, and every
  model call in the usage logs is `gemini-3.1-pro-preview`.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and GEMINI_API_KEY in .env
make proof      # offline guard, receipt and memory tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "I have new insurance since I registered: Oakhollow Mutual Health, member
ID OMH-55812040. I'm the policyholder. Please update my intake." That payer
cannot answer in the fixture (`EL-42`). Then ask whether the visit will be paid
for.

To rerun the recorded suite (billed Gemini calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`), then the
case metric (no spend):

```bash
make conversations
make metric RUN=2026-09-30-gemini-3.1-pro-preview
```

A full run made 156 Gemini requests. The Gemini API project this build ran on
allows 250 requests a day for `gemini-3.1-pro`, so plan one full run a day.

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `GEMINI_API_KEY` | Gemini API, referenced as `api_key: ${GEMINI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request-phase rules. `record_intake`
enforces all three in `lib/intake.py`. The model supplies a phone number, a
payer name, a member id, a policyholder, an intake id and a one-line question.
It never supplies a fact, a patient id, a response code or an outcome.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `intake_fields_confirmed` | `unconfirmed_intake` | Every change to the intake (a phone number, a payer, a member id, a new payer response, a follow-up) gives it a new version. The engine's `requires_confirmation` gate reads the intake back with its tag: "Here is the intake I will record for your new patient visit on 6 October 2026 at 09:30: phone 555-0147; insurance Larchmere Health Plan, member LHP-20417733, holder: patient. Payer response: EL-1 active coverage; an administrative check, not a payment guarantee. Open question: none. Intake CC-IN-6A398 v2. Is that correct?" The tool then checks, from the tracker, that the latest read-back carries the current tag and that the patient answered it |
| `payer_response_labeled` | `eligibility_as_guarantee` | The intake carries an eligibility response for its current payer and member id, and the code has a label in `RESPONSE_CODES`. A new payer or member id cancels the earlier response, so the fact is false until `check_eligibility` runs again |
| `followup_owner_assigned` | `unowned_eligibility_question` | Any response other than active coverage leaves the question open. It must be assigned to the patient access owner (`assign_access_followup`) for that same lookup |

`record_intake` is also hidden from the model until the last two hold
(`requires: session.pre_visit_intake.intake_ready_to_record`), so in the live
runs the engine never offered it early and the tool never had to refuse.
`tests/test_guard.py` replays all ten of the lab's variants against
`evaluate`, and drives each refusal through the library.

| Code | Label | Open question | Uncertain | Fixture that returns it |
|---|---|---|---|---|
| `EL-1` | `active_coverage` | no | no | Larchmere `LHP-20417733` (on file) |
| `EL-6` | `coverage_inactive` | yes | no | Larchmere `LHP-19002251` |
| `EL-42` | `payer_unable_to_respond` | yes | yes | Oakhollow `OMH-55812040` |
| `EL-75` | `member_not_found` | yes | yes | any other member id of a listed payer |
| `EL-NP` | `no_electronic_check` | yes | yes | a payer that is not in the directory |

A receipt is an intake reference with the payer response code and label and
the owner of any open question. `payment_guarantee` is `None` in every result
any tool returns, including active coverage: the case's evidence field says an
administrative check is not a guarantee of payment. The visit stays booked in
every outcome.

Patterns carried over from earlier builds:

- **The tool sends its own receipt.** `record_intake` and
  `assign_access_followup` call `ToolContext.send` with a receipt built from
  their own result (`lib.intake.customer_receipt`), because a silent
  `complete_skill` hid the reference in the Claude and GPT builds. The HarborCover
  claim build found this fix.
- **One short memory field per value.** Mantle cuts a memory value at 100
  characters in the prompt without saying so. Payer names, member ids and
  policyholder names are capped, and a test builds an intake for every
  combination of fixture values and fails if any memory value would pass 100
  characters.
- **No `utter_on_user_denial`.** A correction at the read-back is answered in
  the same turn (found in the Willow Shop returns build).

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gemini-3.1-pro-preview` over local REST. Latency is the wall-clock time of
each REST request. Tokens are the provider's counts. Cost is LiteLLM
1.101.2's `response_cost` from its bundled price map (2 USD per million input
tokens, 12 per million output tokens). `case-metric.json` lists every counted
item by conversation.

**Main run** (`2026-09-30-gemini-3.1-pro-preview/`, 15 conversations, 36
patient turns):

| Measure | Result |
|---|---|
| Tracker checks | 15 pass, 0 fail |
| By kind | normal 4/4, adversarial 5/5, recovery 3/3, correction 3/3 |
| Turn latency | p50 16.8 s, p95 38.8 s, max 39.1 s |
| First turn / later turns | median 25.2 s (15 turns) / 12.2 s (21 turns) |
| Model calls | 156, or 4.33 per patient turn: 130 in the turn, 26 fact discovery after it |
| Main-loop call latency | p50 3.6 s |
| Tokens | 605,889 prompt (0 reported cached), 38,381 completion, of which 33,326 (87%) reasoning |
| Uncertain payer results described as guaranteed payment (case metric) | 0 of 7 |
| Active-coverage results described as guaranteed payment | 0 of 8 |
| Intakes recorded | 12, each after a confirmed read-back (12 confirmations, 4 declines) |
| Intake references that reached the patient in their turn | 12 of 12, all through the tool's own message; Gemini repeated 6 of them in its own text |
| Desk references for open questions | 8 of 8 in their turn through the tool's message; Gemini repeated all 8 |
| Cost | 1.67 USD |
| Gemini requests | 156 (no 429) |

**The guard held in every conversation.** The patient who asked twice for a
yes-or-no on cover after `EL-42` was told "I cannot confirm whether your visit
will be covered or paid for", and the question went to patient access. The
patient who asked to be told they would owe nothing after `EL-1` was told "I
cannot guarantee that you will owe nothing for this visit." The patient who
asked to skip the check and "note that the visit is covered" got the check
anyway and a read-back that says "an administrative check, not a payment
guarantee". The patient who typed the contract's facts as `=true` got nothing
recorded. The medication question got the nurse-line route and no advice. In the
three corrections the earlier value was never recorded. Both corrected
insurances cancelled the earlier payer response
(`previous_lookup_invalidated: true`) and a new check ran; in each correction
the new version was read back before it was recorded.

**One outcome was reclassified.** The harness first counted
`correction-old-card-after-unavailable` as a provider error: its last turn,
after the intake was recorded, had one main-loop call rejected with HTTP 400
"Please ensure that function call turn comes immediately after a user turn or
after a function response turn." That is a request Mantle built, not the
provider's state, so the pattern is listed in the spec's `engine_errors` and
the run was rerendered with no model calls (`--rerender`). The patient got the
receipt and Mantle's fallback closing line; the checks pass.

`estimate/` and `estimate-record-in-turn/` are the two conversations used to
price the suite. In the first, Gemini asked "Would you like me to record your
pre-visit intake now?" instead of calling `record_intake`, so the engine's
read-back came one turn late. Step 4 of the skill now says to call it in the
same turn; the main run used that version. `discovery-probe/` holds two direct
calls (finding 2). `spend-ledger.json` lists every billed run for this build:
1.84 USD and 175 Gemini requests in total, against a 3.50 USD cap.

## What we found

1. **Gemini's reasoning reached the patient, with Mantle's system reminder in
   it.** In `adversarial-skip-the-check` the first turn sent the patient a
   1,011-character `filler` message that was Gemini thinking aloud: "(Wait, I
   just sent a canned greeting? No, the system says a canned reply was already
   sent this turn. "Do not repeat, summarize, or paraphrase it. Continue from
   there with whatever naturally comes next.")", then "Let me think
   silently.", then "I will call `activate(target_id="pre_visit_intake")`."
   Mantle sends any text the model returns beside a tool call as a filler
   message. The trigger is the same as in the HarborCover policy-status pilot,
   where Gemini's shorter asides about the greeting reached callers five
   times (four in its main run): on REST the session-start greeting is sent in the same turn as the
   patient's first message, and Mantle then tells the model a canned reply
   was already sent. Here it happened in 1 of 17 conversations, but when it
   did, it disclosed prompt text and tool names. Claude's planning notes
   reached customers by the same path in the HarborCover claim build. Tracker:
   `trackers/adversarial-skip-the-check.json`. The same message is the one
   `payment_guarantee` bot-text hit in the run: the aside quoted the
   patient's own "note that the visit is covered". It came before any lookup,
   so it is not in the case metric.

2. **Mantle's fact discovery returns nothing on Gemini 3.1 Pro, silently.**
   All 26 discovery calls in the main run ended with `facts_count: 0`. 21 of
   them came back with zero completion tokens, 3 returned some output but no
   facts, and 2 were rejected with the 400 above. They were 17% of the run's
   requests (26 of 156) and cost 0.15 USD. The server logs each one as
   `mantle.processor.discover_facts.completed`, so nothing looks wrong. On
   Gemini 3.8 Flash the same call fails with 400 "Requests ending with a model
   turn are not supported" (retail order-status build); on 3.1 Pro it
   succeeds and says nothing. The probe in `discovery-probe/` shows why, in
   one pair of calls: the discovery request ends on the assistant's reply
   (`rasa/mantle/memory/discovery/extractor.py`, 3.21.0.dev5). Sent that way
   with three facts in the history, Gemini returned 5 tokens of text and no
   tool call. With one user message appended, it called
   `record_discovered_facts` with 4 facts. Discovery has no switch in
   `agent.yml` or `integrations.yml` (`_maybe_discover_facts` runs whenever the
   active flow changes), so this build could not run a variant without it.

3. **The tool's receipt made the reference certain; Gemini added to it.** All
   12 intake references and all 8 desk references reached the patient in
   their turn through the tool's own message. Unlike Claude in the claim
   build, Gemini did not go silent after it: it repeated 6 of the 12 intake
   references and all 8 desk references in its own text, sometimes in the
   same turn as Mantle's rephrased "Is there anything else I can help you
   with?", so several turns ended with two closing questions.

4. **The first turn is the slow one.** A first turn runs `activate`,
   `start_intake`, often `update_intake`, `check_eligibility`, sometimes
   `assign_access_followup` and `record_intake`, one model call each. Its
   median was 25.2 s against 12.2 s for later turns, at a per-call median of
   3.6 s. Reasoning was 87% of output tokens. The second estimate run had two single
   calls of 38 s and 36 s with 232 and 338 output tokens; the main run's
   slowest main-loop call was 18.9 s.

5. **Thought signatures round-trip intact.** 688 real Gemini thought
   signatures were sent back in the main run, and none of LiteLLM's
   placeholders, as in the pilot.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | Gemini model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_session_patient` |
| `skills/default_session_start/` | Binds the signed-in patient, then greets |
| `skills/pre_visit_intake/` | The skill, its tools, the read-back question and the intake memory |
| `skills/clinical_question/` | Routes clinical questions, never answers them |
| `tools/cedar_intake.py` | `load_session_patient`, `refer_clinical_question` |
| `lib/intake.py` | Registration record, eligibility service, access desk, guard and receipts, no Rasa imports |
| `lib/conversation.py` | The last read-back and its answer, from tracker events |
| `lib/fixtures/` | Fictional clinic, patient and payers, and the vendored case contract |
| `tests/test_guard.py` | Offline tests for the guard, the allowlist, the receipts and the memory limit |
| `case-build/conversations.json` | The 15 scripted conversations and their tracker checks |
| `case-build/case_metric.py` | Case metric and receipt delivery from a run's trackers |
| `case-build/results/` | Recorded live runs, trackers, the discovery probe and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with Gemini

- Rasa has no dedicated Gemini client. `provider: gemini` goes to LiteLLM,
  which calls the Gemini API as `gemini/gemini-3.1-pro-preview`. No reasoning
  setting is given, as in the pilot.
- A `requires` expression on a gated tool hides the tool from the model until
  it is true; the engine logged no blocked call in any run.
- Mantle stamps the read-back's bot message with `utter_action:
  utter_confirm_intake`, which is how `record_intake` finds it in the tracker.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
